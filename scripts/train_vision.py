"""Train the offline photo classifier: a linear probe on frozen CLIP embeddings.

Same datasets, label mapping and split as eval_vision.py, so the LLM test set is never trained on:
    python scripts/train_vision.py              # train on the train split, report on the test split
    python scripts/train_vision.py --per-label 40

Writes data/processed/vision/clf_head.npz (W, b, labels) and clf_report.json. The backend picks the head up
automatically (VISION_PROVIDER=local, or as the second vote next to Gemini).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_vision import discover, split

from backend.app.services.vision import _load, local

MIN_PER_LABEL = 10


def embed(items: list[tuple[Path, str]]) -> tuple[np.ndarray, list[str]]:
    return local.embed([_load(p)[0] for p, _ in items]), [lab for _, lab in items]


def main() -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report

    ap = argparse.ArgumentParser()
    ap.add_argument("--per-label", type=int, default=40, help="test images per label (held out, as in eval_vision)")
    ap.add_argument("--C", type=float, default=2.0)
    args = ap.parse_args()

    found = discover()
    if not found:
        sys.exit("nothing found - put the datasets under data/raw/ (see eval_vision.py)")
    _, test, train = split(found, args.per_label)
    counts = Counter(lab for _, lab in train)
    keep = {lab for lab, n in counts.items() if n >= MIN_PER_LABEL}
    print("train per label:", dict(counts), "| dropped (too few):", sorted(set(counts) - keep) or "none")
    if len(keep) < 3:
        sys.exit("need at least 3 labels with enough photos")
    train = [x for x in train if x[1] in keep]
    test = [x for x in test if x[1] in keep]

    Xtr, ytr = embed(train)
    clf = LogisticRegression(C=args.C, max_iter=2000, class_weight="balanced").fit(Xtr, ytr)
    report = {"train": len(train), "labels": list(clf.classes_)}
    if test:
        Xte, yte = embed(test)
        report["test"] = classification_report(yte, clf.predict(Xte), output_dict=True, zero_division=0)
        print(classification_report(yte, clf.predict(Xte), zero_division=0))

    out = local.HEAD_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    # sklearn scores = X @ coef_.T + intercept_; local.scores() applies the same softmax
    np.savez_compressed(out, W=clf.coef_.T.astype("float32"), b=clf.intercept_.astype("float32"),
                        labels=np.array(clf.classes_))
    (out.parent / "clf_report.json").write_text(json.dumps(report, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
