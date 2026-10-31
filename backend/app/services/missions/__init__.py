"""Zone-only spray mission: lawnmower route inside the zone, exported as ArduPilot .waypoints."""
import math
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from backend.app.services.mapping import geo

DRONE_SPEED_M_S = 3.0   # typical agri-drone spray speed


def _long_axis_angle(zone: BaseGeometry) -> float:
    rect = zone.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    edges = [(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(4)]
    dx, dy = max(edges, key=lambda e: math.hypot(*e))
    return math.degrees(math.atan2(dy, dx))


def lawnmower(zone_m: BaseGeometry, swath_m: float, buffer_m: float) -> list[tuple[float, float]]:
    """Back-and-forth passes along the zone's long axis, spaced one swath apart. Metric coordinates."""
    area = zone_m.buffer(buffer_m)
    angle = _long_axis_angle(area)
    centre = area.centroid
    flat = affinity.rotate(area, -angle, origin=centre)
    minx, miny, maxx, maxy = flat.bounds

    pts, y, flip = [], miny + swath_m / 2, False
    while y < maxy:
        seg = flat.intersection(LineString([(minx - 1, y), (maxx + 1, y)]))
        if not seg.is_empty:
            parts = [seg] if seg.geom_type == "LineString" else list(getattr(seg, "geoms", []))
            for part in sorted(parts, key=lambda p: p.bounds[0], reverse=flip):
                a, b = part.coords[0], part.coords[-1]
                pts += [b, a] if flip else [a, b]
        y += swath_m
        flip = not flip
    return [tuple(affinity.rotate(Point(p), angle, origin=centre).coords[0]) for p in pts]


def plan_route(zone_wgs: dict, swath_m: float, buffer_m: float, altitude_m: float) -> dict:
    zone_m = geo.to_m(zone_wgs)
    path_m = lawnmower(zone_m, swath_m, buffer_m)
    length = sum(math.dist(path_m[i], path_m[i + 1]) for i in range(len(path_m) - 1))
    line = geo.to_wgs(LineString(path_m)) if len(path_m) >= 2 else None
    takeoff = path_m[0] if path_m else tuple(zone_m.centroid.coords[0])
    return {
        "path": line,
        "waypoints": [list(c) for c in (line["coordinates"] if line else [])],
        "passes": len(path_m) // 2,
        "length_m": round(length),
        "minutes": round(length / DRONE_SPEED_M_S / 60, 1),
        "swath_m": swath_m,
        "altitude_m": altitude_m,
        "takeoff": list(geo.to_wgs(Point(takeoff))["coordinates"]),
        "inside_zone_buffer_m": buffer_m,
    }


def waypoints_file(route: dict, out: Path) -> Path:
    """QGC WPL 110: home, takeoff, spray on, waypoints, spray off, RTL."""
    lon0, lat0 = route["takeoff"]
    alt = route["altitude_m"]
    rows = [(0, 1, 0, 16, 0, 0, 0, 0, lat0, lon0, 0, 1),
            (1, 0, 3, 22, 0, 0, 0, 0, lat0, lon0, alt, 1),
            (2, 0, 3, 216, 1, 0, 0, 0, 0, 0, 0, 1)]          # DO_SPRAYER on
    for lon, lat in route["waypoints"]:
        rows.append((len(rows), 0, 3, 16, 0, 0, 0, 0, lat, lon, alt, 1))
    rows.append((len(rows), 0, 3, 216, 0, 0, 0, 0, 0, 0, 0, 1))  # DO_SPRAYER off
    rows.append((len(rows), 0, 3, 20, 0, 0, 0, 0, 0, 0, 0, 1))   # RTL
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["QGC WPL 110"] + ["\t".join(f"{v:.7f}" if isinstance(v, float) else str(v) for v in r) for r in rows]
    out.write_text("\n".join(lines) + "\n")
    return out
