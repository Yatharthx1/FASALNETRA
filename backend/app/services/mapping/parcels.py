"""Which land parcel (khasra) a phone is standing in, from the farmer's GPS.

Production: village cadastral maps (Bhu-Naksha / AgriStack) with the farmer's consent. Hackathon: the dummy
village parcels in ../khasra_demo/khasra_data.geojson, else the parcels around the demo field.
Owner names are never returned: a farmer's phone must not learn who owns the next field.
"""
import json
from functools import lru_cache
from pathlib import Path

from shapely.strtree import STRtree

from backend.app.core.config import settings
from backend.app.services.mapping import geo

REPO_ROOT = Path(__file__).resolve().parents[4]
VILLAGE_PARCELS = REPO_ROOT.parent / "khasra_demo" / "khasra_data.geojson"


@lru_cache
def _parcels() -> tuple[list[dict], list, STRtree]:
    path = VILLAGE_PARCELS if VILLAGE_PARCELS.exists() else settings.demo_field_geojson
    # parcels with no map shape (not every village map is geo-referenced) cannot be matched by GPS
    feats = [f for f in json.loads(path.read_text(encoding="utf-8"))["features"] if f.get("geometry")]
    shapes = [geo.to_m(f["geometry"]) for f in feats]
    return feats, shapes, STRtree(shapes)


def locate(lon: float, lat: float, field_geometry: dict, accuracy_m: float = 10.0) -> dict:
    """Where the phone is relative to the farmer's mapped field, and which parcel it is in."""
    p = geo.to_m({"type": "Point", "coordinates": [lon, lat]})
    field = geo.to_m(field_geometry)
    distance = round(field.boundary.distance(p) if not field.contains(p) else 0.0, 1)
    feats, shapes, tree = _parcels()
    hits = [i for i in tree.query(p) if shapes[i].contains(p)]
    parcel = None
    if hits:
        props = feats[hits[0]]["properties"]
        parcel = {"khasra": props.get("khasra"), "village_id": props.get("village_id"),
                  "area_ha": props.get("area_ha"), "recorded_crop": props.get("recorded_crop")}
    if field.contains(p) or distance <= accuracy_m:
        status = "on_field"           # inside, or within the GPS error of the boundary
    elif distance <= 150:
        status = "near_field"         # at the bund / next field: guide them in
    else:
        status = "away"               # not at this field: wrong parcel on record, or walking from home
    same = parcel is not None and field.intersection(shapes[hits[0]]).area > 0.5 * shapes[hits[0]].area
    return {"status": status, "distance_m": distance, "accuracy_m": round(accuracy_m, 1),
            "parcel": parcel, "parcel_is_mapped_field": same}
