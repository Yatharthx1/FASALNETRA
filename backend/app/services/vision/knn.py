"""Second photo vote: nearest labelled Indian soybean photos in CLIP embedding space.

Independent of the LLM, so when both agree the evidence is stronger.
Index is built by scripts/eval_vision.py --build-index from the training split.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.app.services.vision import LABELS, VISION_DIR, _load

INDEX_FILE = VISION_DIR / "knn_index.npz"
MODEL_NAME = "clip-ViT-B-32"
K = 7


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def embed(paths: list[Path], batch: int = 32) -> np.ndarray:
    imgs = [_load(p)[0] for p in paths]
    return _model().encode(imgs, batch_size=batch, normalize_embeddings=True, show_progress_bar=len(imgs) > 50)


def build(paths: list[Path], labels: list[str]) -> None:
    np.savez_compressed(INDEX_FILE, emb=embed(paths), labels=np.array(labels))


@lru_cache
def _index():
    d = np.load(INDEX_FILE)
    return d["emb"], d["labels"]


def available() -> bool:
    return INDEX_FILE.exists()


def vote(image: bytes | str | Path) -> dict:
    emb, labels = _index()
    q = _model().encode([_load(image)[0]], normalize_embeddings=True)[0]
    sims = emb @ q
    top = np.argsort(-sims)[:K]
    w = np.maximum(sims[top], 0)
    scores = {lab: float(w[labels[top] == lab].sum() / max(w.sum(), 1e-6)) for lab in LABELS}
    best = max(scores, key=scores.get)
    return {"label": best, "confidence": round(scores[best], 3), "scores": scores,
            "neighbours": int((labels[top] == best).sum())}
