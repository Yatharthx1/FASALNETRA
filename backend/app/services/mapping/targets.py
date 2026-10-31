"""Turn the blurry 10 m Sentinel-2 grid into a short walk the farmer can actually do.

One weak pixel is noise and three adjacent weak pixels are one patch, so flagged cells are first merged
into patches. Each patch gets one stop (its weakest cell); a big patch gets a second stop at its far end
so the photos show how far it spreads. Stops closer together than phone GPS can tell apart are dropped,
and the stops are ordered as a walking route from the field corner.

Satellite shows nothing? The farmer still called about a problem, so the walk goes where the field profile
says to look: low spots (water collects), the border when it is grassy or next to urad/moong (whitefly
and pests come in from there), else the weakest cell. The walk is never empty.
"""
import re
from math import cos, hypot, radians

from shapely.ops import unary_union

from backend.app.services.mapping import geo

CELL_M2 = 100.0         # one Sentinel-2 10 m cell
MIN_GAP_M = 12.0        # stops closer than this look the same to phone GPS
BIG_PATCH_CELLS = 4     # a patch this big gets a second stop at its far end
BORDER_M = 10.0         # cell centre within this of the field edge = border cell
WEAK_Z = -0.8           # below its usual standing, though not enough to be flagged

_RC = re.compile(r"r(\d+)c(\d+)")


def _rc(cell: dict) -> tuple[int, int]:
    m = _RC.fullmatch(cell["id"])
    return (int(m[1]), int(m[2])) if m else (0, 0)


def _weakness(cell: dict) -> float:
    return -min(cell.get("z_ndvi") or 0.0, cell.get("z_ndre") or 0.0)


def patches(cells: list[dict]) -> list[list[dict]]:
    """Flagged cells grouped by 8-neighbour adjacency, strongest patch first."""
    flagged = {_rc(c): c for c in cells if c["flagged"]}
    seen: set[tuple[int, int]] = set()
    groups = []
    for start in flagged:
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            r, c = stack.pop()
            group.append(flagged[(r, c)])
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in flagged and n not in seen:
                        seen.add(n)
                        stack.append(n)
        groups.append(group)
    return sorted(groups, key=lambda g: -sum(_weakness(c) for c in g))


def _metres(a: list[float], b: list[float]) -> float:
    """Equirectangular distance; plenty for points inside one field."""
    k = 111_320.0
    return hypot((a[0] - b[0]) * k * cos(radians((a[1] + b[1]) / 2)), (a[1] - b[1]) * k)


def _stop(cell: dict, reason: str, patch: list[dict] | None = None) -> dict:
    out = {"id": cell["id"], "centre": cell["centre"], "polygon": cell["polygon"], "visited": False, "reason": reason}
    if patch:
        out["patch_cells"] = len(patch)
        out["patch_acres"] = round(len(patch) * CELL_M2 / geo.M2_PER_ACRE, 2)
        out["patch"] = geo.to_wgs(unary_union([geo.to_m(c["polygon"]) for c in patch]))
    return out


def _fallback(cells: list[dict], field: dict, profile: dict | None) -> list[dict]:
    edge = geo.to_m(field).boundary
    inside = [c for c in cells if geo.to_m({"type": "Point", "coordinates": c["centre"]}).within(geo.to_m(field))] or cells
    by_weak = sorted(inside, key=_weakness, reverse=True)
    stops = []
    low = [c for c in by_weak if c.get("low_spot") and _weakness(c) >= -WEAK_Z]
    if low:
        stops.append(_stop(low[0], "low_spot"))
    profile = profile or {}
    if profile.get("grassy_border") == "yes" or profile.get("neighbor_crop") == "urad_moong":
        border = [c for c in by_weak
                  if geo.to_m({"type": "Point", "coordinates": c["centre"]}).distance(edge) <= BORDER_M]
        if border:
            stops.append(_stop(border[0], "border"))
    if by_weak:
        stops.append(_stop(by_weak[0], "weakest"))
    return stops


def _route(stops: list[dict], start: list[float]) -> list[dict]:
    """Greedy nearest-next walk from the field corner."""
    left, here, out = list(stops), start, []
    while left:
        nxt = min(left, key=lambda s: _metres(here, s["centre"]))
        left.remove(nxt)
        out.append(nxt)
        here = nxt["centre"]
    return out


def pick(cells: list[dict], field: dict, profile: dict | None = None, n: int = 3) -> list[dict]:
    stops: list[dict] = []
    groups = patches(cells)
    for g in groups:
        stops.append(_stop(max(g, key=_weakness), "satellite_patch", g))
    if groups and len(groups[0]) >= BIG_PATCH_CELLS:
        first = stops[0]["centre"]
        far = max(groups[0], key=lambda c: _metres(first, c["centre"]))
        stops.insert(1, _stop(far, "patch_edge"))
    if not stops:
        stops = _fallback(cells, field, profile)

    kept: list[dict] = []
    for s in stops:
        if all(_metres(s["centre"], k["centre"]) >= MIN_GAP_M for k in kept):
            kept.append(s)
        if len(kept) == n:
            break
    return _route(kept, field["coordinates"][0][0])
