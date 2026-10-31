"""Offline photo classifier: CLIP image embedding + a small trained head. No internet, no API key.

Used as the main model when no Gemini key is set (VISION_PROVIDER=local, or a rural demo with no data),
and as an independent second vote next to the LLM.

    head trained   data/processed/vision/clf_head.npz from scripts/train_vision.py (linear probe on the
                   Indian soybean datasets): calibrated softmax over LABELS
    no head yet    zero-shot: image vs. one text description per label (weaker; confidence is capped)
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from backend.app.services.vision import LABEL_HINTS, LABELS, VISION_DIR, _load
from backend.app.services.vision.knn import _model

HEAD_FILE = VISION_DIR / "clf_head.npz"
ZERO_SHOT_TEMP = 100.0      # CLIP logit scale
ZERO_SHOT_MAX_CONF = 0.6    # zero-shot is a weak vote: never let it reach "high" on its own
PESTS = {"yellow_mosaic", "chewing_damage", "girdle_beetle", "fungal"}


def head_trained() -> bool:
    return HEAD_FILE.exists()


def available() -> bool:
    """The CLIP weights load lazily (~600 MB on first use); the package must be installed."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def embed(images: list) -> np.ndarray:
    return _model().encode(images, normalize_embeddings=True, batch_size=32, show_progress_bar=len(images) > 50)


@lru_cache
def _head() -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    if not HEAD_FILE.exists():
        return None
    d = np.load(HEAD_FILE)
    return d["W"], d["b"], [str(x) for x in d["labels"]]


@lru_cache
def _text_embeddings() -> np.ndarray:
    prompts = [f"a close-up phone photo of a soybean leaf: {LABEL_HINTS[lab]}" for lab in LABELS if lab != "unsure"]
    return _model().encode(prompts, normalize_embeddings=True)


def _softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(z - z.max())
    return e / e.sum()


def scores(image: Image.Image | bytes | str | Path) -> tuple[dict[str, float], str]:
    img = image if isinstance(image, Image.Image) else _load(image)[0]
    q = embed([img])[0]
    head = _head()
    if head is not None:
        W, b, labels = head
        return dict(zip(labels, _softmax(q @ W + b).tolist(), strict=True)), "clip_linear_probe"
    labels = [lab for lab in LABELS if lab != "unsure"]
    return dict(zip(labels, _softmax(ZERO_SHOT_TEMP * (_text_embeddings() @ q)).tolist(), strict=True)), "clip_zero_shot"


def classify(image: Image.Image | bytes | str | Path) -> dict:
    """Same shape as the LLM answer, so the rest of the pipeline does not care which model ran."""
    s, model = scores(image)
    label = max(s, key=s.get)
    conf = s[label] if model == "clip_linear_probe" else min(s[label], ZERO_SHOT_MAX_CONF)
    if conf < 0.35:
        label = "unsure"
    severity = 0 if label in ("healthy", "unsure") else 2 if label in PESTS and conf >= 0.5 else 1
    return {"label": label, "confidence": round(float(conf), 3), "severity": severity, "whitefly_visible": False,
            "symptoms_seen": f"{model}: " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(s.items(), key=lambda x: -x[1])[:3]),
            "model": model, "scores": {k: round(v, 3) for k, v in s.items()}}
