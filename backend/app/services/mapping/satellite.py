"""Satellite scout: flag the 10 m grid cells of a field that are getting weaker.

Works only on the cache written by scripts/fetch_field_data.py.

A cell is compared with the rest of its own field on the same day (this cancels
haze, crop growth and whole-field effects), and that relative standing is then
compared with the cell's own history. A cell that used to be average and is now
clearly below the field is flagged. Sentinel-2 is a scout: it says *where* to
look, never *what* is wrong.
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import box, mapping, shape

REPO_ROOT = Path(__file__).resolve().parents[4]
PROCESSED = REPO_ROOT / "data" / "processed"
M2_PER_ACRE = 4046.86

Z_FLAG = -1.5          # cell is 1.5 of its own usual spread below where it normally sits in the field
MIN_HISTORY = 4        # clear scenes needed before a cell has a usable history
LOW_SPOT_M = -0.3      # relative elevation below which water collects


@lru_cache
def load(field_id: str) -> dict:
    d = PROCESSED / field_id
    meta = json.loads((d / "meta.json").read_text())
    s2 = dict(np.load(d / "s2_stack.npz"))
    terrain = dict(np.load(d / "terrain.npz")) if (d / "terrain.npz").exists() else None
    return {"meta": meta, "s2": s2, "terrain": terrain,
            "transform": rasterio.Affine(*meta["transform"]), "crs": meta["crs"]}


def field_mask(field_id: str, geometry: dict, all_touched: bool = True) -> np.ndarray:
    """all_touched=True: every cell the field touches (for drawing the grid).
    False: only cells whose centre is inside, so edge pixels mixed with the neighbour's land are never flagged."""
    c = load(field_id)
    geom = transform_geom("EPSG:4326", c["crs"], geometry)
    return ~geometry_mask([geom], out_shape=tuple(c["meta"]["shape"]), transform=c["transform"], all_touched=all_touched)


def _relative_z(stack: np.ndarray, clear: np.ndarray, inside: np.ndarray, t: int) -> tuple[np.ndarray, np.ndarray]:
    """Relative standing (value minus field median) at scene t, as a z-score against earlier scenes."""
    rel = np.full(stack.shape, np.nan, dtype="float32")
    for k in range(stack.shape[0]):
        ok = clear[k] & inside & np.isfinite(stack[k])
        if ok.sum() >= 3:
            rel[k] = np.where(clear[k], stack[k] - np.median(stack[k][ok]), np.nan)
    hist = rel[:t]
    n = np.isfinite(hist).sum(axis=0)
    mu = np.nanmean(np.where(n >= MIN_HISTORY, hist, np.nan), axis=0) if t else np.full(rel[0].shape, np.nan)
    sd = np.nanstd(np.where(n >= MIN_HISTORY, hist, np.nan), axis=0) if t else np.full(rel[0].shape, np.nan)
    z = (rel[t] - mu) / np.maximum(sd, 0.02)
    return z, rel[t]


def scene_index(field_id: str, on: date) -> int:
    dates = [date.fromisoformat(str(d)) for d in load(field_id)["s2"]["dates"]]
    before = [i for i, d in enumerate(dates) if d <= on]
    if not before:
        raise ValueError(f"No clear Sentinel-2 scene on or before {on}")
    return before[-1]


def scan(field_id: str, geometry: dict, on: date) -> dict:
    """Grid cells for the field on a date, with flags, plus a summary vote for the evidence card."""
    c = load(field_id)
    s2, inside = c["s2"], field_mask(field_id, geometry)
    core = field_mask(field_id, geometry, all_touched=False)
    t = scene_index(field_id, on)
    clear = s2["clear"]

    z_ndvi, rel_ndvi = _relative_z(s2["ndvi"], clear, core, t)
    z_ndre, _ = _relative_z(s2["ndre"], clear, core, t)
    z_ndmi, _ = _relative_z(s2["ndmi"], clear, core, t)
    weak = core & clear[t] & (np.fmin(z_ndvi, z_ndre) < Z_FLAG) & (rel_ndvi < 0)

    rel_elev = c["terrain"]["rel_elev"] if c["terrain"] else np.zeros_like(z_ndvi)
    slope = c["terrain"]["slope"] if c["terrain"] else np.zeros_like(z_ndvi)
    low = rel_elev < LOW_SPOT_M

    labels, n_patches = ndimage.label(weak)
    biggest = np.bincount(labels[labels > 0]).max() if n_patches else 0
    n_in, n_weak = int(core.sum()), int(weak.sum())
    frac = n_weak / max(n_in, 1)
    if n_weak == 0:
        pattern = "none"
    elif frac > 0.6:
        pattern = "field_wide"     # whole field -> nutrient / water / sowing, not a spreading pest
    elif biggest >= 0.6 * n_weak:
        pattern = "patch"          # one compact patch -> what a spreading pest or disease looks like
    else:
        pattern = "scattered"

    px_area = abs(c["transform"].a * c["transform"].e)
    cells = []
    rows, cols = np.nonzero(inside)
    for r, col in zip(rows, cols, strict=True):
        x0, y0 = c["transform"] @ (col, r)
        x1, y1 = c["transform"] @ (col + 1, r + 1)
        poly = transform_geom(c["crs"], "EPSG:4326", mapping(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))))
        cells.append({
            "id": f"r{r}c{col}",
            "polygon": poly,
            "centre": list(shape(poly).centroid.coords[0]),
            "ndvi": _f(s2["ndvi"][t][r, col]),
            "z_ndvi": _f(z_ndvi[r, col]), "z_ndre": _f(z_ndre[r, col]), "z_ndmi": _f(z_ndmi[r, col]),
            "low_spot": bool(low[r, col]), "slope_deg": _f(slope[r, col]),
            "flagged": bool(weak[r, col]),
        })

    weak_z = np.fmin(z_ndvi, z_ndre)[weak]
    strength = float(np.clip((-weak_z.mean() - 1.0) / 2.0, 0, 1)) if n_weak else 0.0
    return {
        "scene_date": str(s2["dates"][t]),
        "cells": cells,
        "summary": {
            "cells_in_field": n_in,
            "cells_flagged": n_weak,
            "flagged_acres": round(n_weak * px_area / M2_PER_ACRE, 2),
            "pattern": pattern,
            "strength": round(strength, 2),
            "low_spot_overlap": round(float((weak & low).sum()) / n_weak, 2) if n_weak else 0.0,
            # any weak patch loses some leaf water; only an NDMI drop well beyond the NDVI drop points to water stress
            "water_signal": round(float(np.nanmean(z_ndmi[weak] - z_ndvi[weak])), 2) if n_weak else None,
            "worst_cell": min((x for x in cells if x["flagged"]), key=lambda x: min(x["z_ndvi"] or 0, x["z_ndre"] or 0),
                              default=None),
        },
    }


def _f(v) -> float | None:
    return None if v is None or not np.isfinite(v) else round(float(v), 3)
