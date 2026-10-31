"""Test and calibrate the photo AI on Indian soybean datasets. No training.

Put each dataset (unzipped, class folders as published) under data/raw/:
    data/raw/soy-net/...            SoyNet (Jabalpur, MP)
    data/raw/mh-soyahealthvision/... MH-SoyaHealthVision (Maharashtra)
    data/raw/leaf-photos/...        India soybean, Data in Brief 2024
Class folder names are mapped to our labels by keyword (FOLDER_KEYWORDS).

    python scripts/eval_vision.py --per-label 40              # LLM test run + calibration
    python scripts/eval_vision.py --per-label 40 --build-index # also the CLIP nearest-neighbour vote
    python scripts/eval_vision.py --dry-run                   # only show what was found

Writes data/processed/vision/: references/, eval_results.csv, report.json, calibration.json
"""
import argparse
import csv
import json
import random
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services import vision  # noqa: E402

RAW = ROOT / "data" / "raw"
DATASETS = ["soy-net", "mh-soyahealthvision", "leaf-photos"]
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
SEED = 31
CAL_BINS = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]

# first matching keyword in the lower-cased path wins; None = skip that class
FOLDER_KEYWORDS = [
    ("healthy", "healthy"),
    ("mosaic", "yellow_mosaic"), ("ymv", "yellow_mosaic"),
    ("vein necrosis", None), ("vein_necrosis", None), ("dry", None),   # virus/drought classes we do not label
    ("rust", "fungal"), ("septoria", "fungal"), ("frog", "fungal"), ("blight", "fungal"),
    ("spot", "fungal"), ("fungal", "fungal"),
    ("caterpillar", "chewing_damage"), ("semilooper", "chewing_damage"), ("looper", "chewing_damage"),
    ("defoli", "chewing_damage"), ("chew", "chewing_damage"), ("pest", "chewing_damage"),
]


def label_for(path: Path) -> str | None:
    p = "/".join(path.parts).lower()
    for kw, label in FOLDER_KEYWORDS:
        if kw in p:
            return label
    return None


def discover() -> dict[str, list[tuple[Path, str]]]:
    found = defaultdict(list)
    for ds in DATASETS:
        for p in (RAW / ds).rglob("*"):
            if p.suffix.lower() in IMAGE_EXT:
                label = label_for(p.relative_to(RAW / ds).parent)
                if label:
                    found[label].append((p, ds))
    return found


def split(found, per_label: int):
    """Stratified by label, then spread across datasets so one dataset cannot dominate."""
    rng = random.Random(SEED)
    refs, test, train = {}, [], []
    for label, items in found.items():
        by_ds = defaultdict(list)
        for p, ds in items:
            by_ds[ds].append(p)
        for v in by_ds.values():
            rng.shuffle(v)
        pool = [p for group in zip(*[iter(v) for v in by_ds.values()], strict=False) for p in group] if len(by_ds) > 1 else []
        pool += [p for v in by_ds.values() for p in v if p not in set(pool)]
        refs[label] = pool[:2]
        test += [(p, label) for p in pool[2:2 + per_label]]
        train += [(p, label) for p in pool[2 + per_label:]]
    return refs, test, train


def write_references(refs: dict[str, list[Path]]) -> None:
    shutil.rmtree(vision.REFERENCES, ignore_errors=True)
    for label, paths in refs.items():
        (vision.REFERENCES / label).mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(paths):
            shutil.copy(p, vision.REFERENCES / label / f"ref{i}{p.suffix.lower()}")


def calibration(rows: list[dict]) -> dict:
    bins = []
    for lo, hi in CAL_BINS:
        b = [r for r in rows if lo <= r["raw_confidence"] <= hi]
        bins.append({"lo": lo, "hi": hi, "n": len(b),
                     "accuracy": round(sum(r["correct"] for r in b) / len(b), 3) if b else None})
    per_label = {}
    for label in vision.LABELS:
        predicted = [r for r in rows if r["predicted"] == label]
        if len(predicted) >= 5:
            per_label[label] = round(sum(r["correct"] for r in predicted) / len(predicted), 3)
    return {"bins": [b for b in bins if b["accuracy"] is not None], "per_label_precision": per_label}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-label", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--build-index", action="store_true")
    args = ap.parse_args()

    found = discover()
    print("found:", {k: len(v) for k, v in found.items()} or "nothing - put datasets under data/raw/")
    if not found:
        return
    refs, test, train = split(found, args.per_label)
    print(f"references {sum(len(v) for v in refs.values())}, test {len(test)}, index pool {len(train)}")
    if args.dry_run:
        return

    write_references(refs)
    vision.CALIBRATION_FILE.unlink(missing_ok=True)   # measure raw confidence, not last run's calibrated one

    rows, t0 = [], time.time()
    for i, (p, truth) in enumerate(test, 1):
        try:
            r = vision.classify(p)
        except Exception as exc:
            print(f"  error on {p.name}: {exc}")
            continue
        rows.append({"file": str(p.relative_to(RAW)), "truth": truth, "predicted": r["label"],
                     "raw_confidence": r["raw_confidence"], "severity": r["severity"],
                     "blur_ok": r["quality"]["ok"], "correct": r["label"] == truth})
        if i % 20 == 0:
            print(f"  {i}/{len(test)}  running accuracy {sum(x['correct'] for x in rows) / len(rows):.2f}")

    out = vision.VISION_DIR
    with open(out / "eval_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    confusion = Counter((r["truth"], r["predicted"]) for r in rows)
    confused = [{"truth": t, "predicted": p, "n": n} for (t, p), n in confusion.most_common() if t != p][:5]
    per_label_recall = {lab: round(sum(r["correct"] for r in rows if r["truth"] == lab) /
                                   max(1, sum(r["truth"] == lab for r in rows)), 3) for lab in found}
    by_dataset = defaultdict(list)
    for r in rows:
        by_dataset[r["file"].split("\\")[0].split("/")[0]].append(r["correct"])
    cal = calibration(rows)
    vision.CALIBRATION_FILE.write_text(json.dumps(cal, indent=1))

    report = {
        "n_test": len(rows),
        "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 3),
        "accuracy_by_dataset": {k: round(sum(v) / len(v), 3) for k, v in by_dataset.items()},
        "recall_by_label": per_label_recall,
        "most_confused": confused,
        "confusion": [{"truth": t, "predicted": p, "n": n} for (t, p), n in sorted(confusion.items())],
        "calibration": cal,
        "seconds": round(time.time() - t0),
    }

    if args.build_index:
        from backend.app.services.vision import knn
        print("building CLIP index ...")
        knn.build([p for p, _ in train], [lab for _, lab in train])
        knn_pred = [knn.vote(RAW / r["file"])["label"] for r in rows]
        agree = [r for r, k in zip(rows, knn_pred, strict=True) if k == r["predicted"]]
        report["knn_accuracy"] = round(sum(k == r["truth"] for r, k in zip(rows, knn_pred, strict=True)) / len(rows), 3)
        report["llm_knn_agree_rate"] = round(len(agree) / len(rows), 3)
        report["accuracy_when_both_agree"] = round(sum(r["correct"] for r in agree) / len(agree), 3) if agree else None

    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in report if k != "confusion"}, indent=1))


if __name__ == "__main__":
    main()
