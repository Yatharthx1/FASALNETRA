"""Metric geometry for small fields: WGS84 <-> UTM 43N (Mandsaur/Indore)."""
from rasterio.warp import transform_geom
from shapely.geometry import MultiPoint, Point, mapping, shape
from shapely.geometry.base import BaseGeometry

UTM = "EPSG:32643"
M2_PER_ACRE = 4046.86


def to_m(geom: dict) -> BaseGeometry:
    return shape(transform_geom("EPSG:4326", UTM, geom))


def to_wgs(geom: BaseGeometry) -> dict:
    return transform_geom(UTM, "EPSG:4326", mapping(geom))


def acres(geom: dict) -> float:
    return to_m(geom).area / M2_PER_ACRE


def zone_from_walk(trail: list[tuple[float, float]], field: dict) -> BaseGeometry:
    """Farmer's GPS walk around the patch -> polygon in metres, clipped to the field. Hull smooths GPS jitter."""
    pts = to_m({"type": "MultiPoint", "coordinates": [list(p) for p in trail]})
    return MultiPoint(list(pts.geoms)).convex_hull.intersection(to_m(field))


def zone_from_spots(spots: list[tuple[float, float]], field: dict, radius_m: float) -> BaseGeometry:
    """Photo spots with clear damage -> circles merged into one zone, clipped to the field."""
    zone = None
    for lon, lat in spots:
        c = to_m(mapping(Point(lon, lat))).buffer(radius_m)
        zone = c if zone is None else zone.union(c)
    return zone.intersection(to_m(field)) if zone is not None else None
