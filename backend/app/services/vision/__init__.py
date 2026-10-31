"""Photo AI: quality gate -> vision LLM (closed label list, few-shot) -> calibrated confidence.

Optional second, independent vote: nearest neighbours in CLIP embedding space
over the labelled Indian soybean photos (see knn.py).
"""
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[4]
VISION_DIR = REPO_ROOT / "data" / "processed" / "vision"
REFERENCES = VISION_DIR / "references"          # references/<label>/*.jpg, 1-2 per label, never in the test set
CACHE_FILE = VISION_DIR / "llm_cache.json"
CALIBRATION_FILE = VISION_DIR / "calibration.json"

LABELS = ["healthy", "yellow_mosaic", "uniform_yellowing", "chewing_damage", "girdle_beetle", "fungal", "unsure"]
LABEL_HINTS = {
    "healthy": "uniform green leaves, no spots, no holes",
    "yellow_mosaic": "bright yellow and green patches in an irregular mosaic or mottle, usually on younger upper leaves; "
                     "leaf may be crinkled (yellow mosaic virus, spread by whitefly)",
    "uniform_yellowing": "whole leaf evenly pale yellow-green with no mottle, often older lower leaves "
                         "(nutrient shortage or waterlogging, not a pest)",
    "chewing_damage": "holes, eaten edges or skeletonised leaves from caterpillars (semilooper, tobacco caterpillar)",
    "girdle_beetle": "two parallel ring cuts around a leaf stalk or stem, with the leaves above it drooping or dried "
                     "while the rest of the plant is green",
    "fungal": "brown, rusty, grey or water-soaked spots or blight on leaves "
              "(rust, septoria, frog-eye, aerial blight, bacterial blight)",
    "unsure": "photo does not show a soybean leaf clearly, or symptoms fit none of the above",
}

class VisionUnavailable(RuntimeError):
    """No vision provider configured (no API key and not in mock mode)."""


BLUR_MIN = 60.0     # variance of Laplacian on a 512 px grey image; below this the photo is too blurry
DARK_MIN = 40.0     # mean brightness 0-255
MAX_SIDE = 1024

# Shared, unchanging prefix first (instructions, then reference images), the farmer's photo last,
# so the provider can reuse the cached prefix across calls.
PROMPT = """Task: classify one phone photo of soybean leaves taken by a farmer in Madhya Pradesh, India, during the
kharif monsoon. Photos are handheld, often in harsh sun or overcast light, sometimes with soil, hands or weeds in frame.

Labels (choose exactly one):
{labels}

How to decide:
1. First write symptoms_seen: what you actually see (colour pattern, spots, holes, insects, which leaves).
2. Mottled yellow-green mosaic = yellow_mosaic. Even pale yellowing without mottle = uniform_yellowing. Do not
   confuse the two: the wrong one leads to a wrong spray.
3. Rust, septoria, frog-eye and blight are all "fungal"; you do not need to tell them apart.
   Holes in the leaf blade = chewing_damage; ring cuts on a stalk with drooping leaves above = girdle_beetle.
4. If the leaf is out of focus, too far away, or not soybean, answer "unsure". Guessing is worse than "unsure".
5. confidence: your probability (0-1) that the label is correct.
6. severity: 0 none, 1 a few spots, 2 clear damage on many leaves, 3 most of the leaf area affected.
7. whitefly_visible: true only if you can see small white winged insects."""


def quality(img: Image.Image) -> dict:
    # shrink to at most 512 px, keeping the shape; never enlarge: a small leaf crop stretched to 512 x 512 looks
    # blurrier than it is (seen with the phone's leaf crops)
    small = ImageOps.grayscale(img)
    small.thumbnail((512, 512))
    g = np.asarray(small, dtype="float32")
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    blur, bright = float(lap.var()), float(g.mean())
    return {"blur_score": round(blur, 1), "brightness": round(bright, 1),
            "ok": blur >= BLUR_MIN and bright >= DARK_MIN,
            "retake_reason": "dark" if bright < DARK_MIN else "blurry" if blur < BLUR_MIN else None}


def _load(image: bytes | str | Path) -> tuple[Image.Image, bytes]:
    raw = Path(image).read_bytes() if isinstance(image, (str, Path)) else image
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img, raw


def _jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _references() -> list[tuple[str, bytes]]:
    refs = []
    for label in LABELS:
        for p in sorted((REFERENCES / label).glob("*.jp*g"))[:2]:
            refs.append((label, _jpeg(_load(p)[0])))
    return refs


def _cache() -> dict:
    return json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}


def _save_cache(c: dict) -> None:
    VISION_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(c))


def _ask_gemini(jpeg: bytes, refs: list[tuple[str, bytes]]) -> dict:
    from google.genai import types

    from backend.app.services.vision import llm

    schema = {
        "type": "object",
        "properties": {
            "symptoms_seen": {"type": "string"},
            "label": {"type": "string", "enum": LABELS},
            "confidence": {"type": "number"},
            "severity": {"type": "integer"},
            "whitefly_visible": {"type": "boolean"},
        },
        "required": ["symptoms_seen", "label", "confidence", "severity", "whitefly_visible"],
        "propertyOrdering": ["symptoms_seen", "label", "confidence", "severity", "whitefly_visible"],
    }
    labels = "\n".join(f"- {k}: {v}" for k, v in LABEL_HINTS.items())
    parts = [types.Part.from_text(text=PROMPT.format(labels=labels))]
    for label, ref in refs:
        parts += [types.Part.from_text(text=f"Reference example, label = {label}:"),
                  types.Part.from_bytes(data=ref, mime_type="image/jpeg")]
    parts += [types.Part.from_text(text="Now classify this farmer's photo:"),
              types.Part.from_bytes(data=jpeg, mime_type="image/jpeg")]
    config = types.GenerateContentConfig(temperature=0, response_mime_type="application/json", response_schema=schema)
    return llm.ask([types.Content(role="user", parts=parts)], config, json.loads)


def calibrate(label: str, raw_conf: float) -> float:
    """Replace the model's self-reported confidence with its measured accuracy at that confidence."""
    if not CALIBRATION_FILE.exists():
        return raw_conf
    cal = json.loads(CALIBRATION_FILE.read_text())
    for b in cal["bins"]:
        if b["lo"] <= raw_conf <= b["hi"] and b["n"] >= 5:
            acc = b["accuracy"]
            per_label = cal["per_label_precision"].get(label)
            return round(min(acc, per_label) if per_label is not None else acc, 3)
    return raw_conf


def provider() -> str:
    """gemini (LLM, needs a key) | local (offline CLIP model) | mock (fixed answer for demos and tests).
    Unset: gemini when a key is present, else the offline model."""
    p = os.environ.get("VISION_PROVIDER", "").strip().lower()
    if p:
        return p
    return "gemini" if (os.environ.get("VISION_API_KEY") or os.environ.get("GEMINI_API_KEY")) else "local"


def advice(label: str) -> dict | None:
    """What the farmer would use for this photo's cause, straight from the ICAR-NSRI table (never from the model).
    The dose for the actual zone comes later from the evidence plan."""
    from backend.app.services import advisory, evidence

    cause = evidence.PHOTO_TO_CAUSE.get(label)
    row = advisory.find(cause) if cause else None
    if row is None:
        return None
    chem = row["chemical"][0] if row["chemical"] else None
    return {"cause": row["cause"], "name_hi": row["name_hi"], "name_en": row["name_en"], "cultural": row["cultural"],
            "product": chem["product"] if chem else None,
            "dose_per_acre": round(chem["dose_per_ha"] * advisory.HA_PER_ACRE, 1) if chem else None,
            "unit": chem["unit"] if chem else None, "pesticide": chem is not None}


def classify(image: bytes | str | Path, use_cache: bool = True) -> dict:
    img, raw = _load(image)
    q = quality(img)
    key = hashlib.sha256(raw).hexdigest()
    cache = _cache() if use_cache else {}
    which = provider()
    if key in cache and cache[key].get("provider", "gemini") == which:
        out = cache[key]
    else:
        if which == "mock":
            out = {"label": "yellow_mosaic", "confidence": 0.86, "severity": 2, "whitefly_visible": True,
                   "symptoms_seen": "mock result"}
        elif which == "local":
            from backend.app.services.vision import local
            if not local.available():
                raise VisionUnavailable("Offline model needs `pip install sentence-transformers`; "
                                        "or set GEMINI_API_KEY, or VISION_PROVIDER=mock for the demo")
            out = local.classify(img)
        else:
            if not (os.environ.get("VISION_API_KEY") or os.environ.get("GEMINI_API_KEY")):
                raise VisionUnavailable("Vision AI not configured: set GEMINI_API_KEY, VISION_PROVIDER=local "
                                        "for the offline model, or VISION_PROVIDER=mock for the demo")
            out = _ask_gemini(_jpeg(img), _references())
        out["label"] = out["label"] if out["label"] in LABELS else "unsure"
        out["provider"] = which
        cache[key] = out
        if use_cache:
            _save_cache(cache)
    # Only the LLM's self-reported confidence is calibrated; the trained head is calibrated by construction.
    conf = calibrate(out["label"], out["confidence"]) if which == "gemini" else out["confidence"]
    return {**out, "raw_confidence": out["confidence"], "confidence": conf,
            "quality": q, "image_sha256": key, "advice": advice(out["label"])}
