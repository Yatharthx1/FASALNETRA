"""Download and cache everything the demo field needs, once, so the demo never calls these APIs live.

    python scripts/fetch_field_data.py                 # demo field (Rampura, khasra 124)
    python scripts/fetch_field_data.py --skip-s2       # only terrain + soil

Writes to data/processed/<field_id>/:
    s2_stack.npz    Sentinel-2 NDVI / NDRE / NDMI per date on a 10 m grid + cloud mask
    terrain.npz     elevation, slope (deg), relative elevation (low spots) on the same grid
    soil.json       SoilGrids topsoil pH, nitrogen, organic carbon
    meta.json       grid transform, CRS, dates
and data/field-geojson/demo-field.geojson (hero field + neighbours).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import planetary_computer
import pystac_client
import rasterio
import requests
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
KHASRA = ROOT.parent / "khasra_demo" / "khasra_data.geojson"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

HERO = {"village_id": "V001", "khasra": "124", "owner": "Ramesh Patidar", "recorded_crop": "Soybean"}
BUFFER_DEG = 0.003          # ~300 m around the field, so neighbours and context are in the grid
NEIGHBOUR_RADIUS_DEG = 0.004
SEASONS = ["2023-06-15/2023-10-31", "2024-06-15/2024-10-31", "2025-06-15/2025-10-31"]
MAX_CLOUD = 95          # tile-wide cloud; the per-pixel SCL mask decides if the field itself is clear
SCL_BAD = {0, 1, 3, 8, 9, 10, 11}   # no data, saturated, shadow, cloud med/high, cirrus, snow


def prepare_field() -> tuple[str, dict, list]:
    data = json.loads(KHASRA.read_text(encoding="utf-8"))
    feats = [f for f in data["features"] if f["geometry"]]
    hero = next(f for f in feats if f["properties"]["village_id"] == HERO["village_id"]
                and f["properties"]["khasra"] == HERO["khasra"])
    hero["properties"].update(HERO, field_id="demo", role="hero")
    centre = shape(hero["geometry"]).centroid
    neighbours = []
    for f in feats:
        if f is hero:
            continue
        if shape(f["geometry"]).centroid.distance(centre) < NEIGHBOUR_RADIUS_DEG:
            f["properties"]["role"] = "neighbour"
            neighbours.append(f)
    out = ROOT / "data" / "field-geojson" / "demo-field.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": [hero, *neighbours]}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"field: {out.relative_to(ROOT)}  ({len(neighbours)} neighbours)")
    return "demo", hero, neighbours


def read_band(href: str, bounds_wgs84, grid: dict | None, resampling=Resampling.bilinear):
    """Read one band clipped to the bounds. First call defines the 10 m grid; later calls are resampled onto it."""
    with rasterio.open(href) as src:
        b = transform_bounds("EPSG:4326", src.crs, *bounds_wgs84)
        if grid is None:
            win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win).astype("float32")
            grid = {"crs": src.crs.to_string(), "transform": src.window_transform(win), "shape": arr.shape}
            return arr, grid
        dst = np.zeros(grid["shape"], dtype="float32")
        reproject(rasterio.band(src, 1), dst, dst_transform=grid["transform"], dst_crs=grid["crs"],
                  resampling=resampling)
        return dst, grid


def fetch_s2(bounds, out_dir: Path) -> dict:
    catalog = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    items = []
    for season in SEASONS:
        items += catalog.search(collections=["sentinel-2-l2a"], bbox=bounds, datetime=season,
                                query={"eo:cloud_cover": {"lt": MAX_CLOUD}}).item_collection()
    items.sort(key=lambda i: i.datetime)
    print(f"sentinel-2: {len(items)} scenes under {MAX_CLOUD}% cloud")

    grid, dates, ndvi, ndre, ndmi, clear = None, [], [], [], [], []
    for item in items:
        day = item.datetime.strftime("%Y-%m-%d")
        if day in dates:   # two tiles on the same day: keep the first
            continue
        try:
            b8, grid = read_band(item.assets["B08"].href, bounds, grid)
            b4, _ = read_band(item.assets["B04"].href, bounds, grid)
            b5, _ = read_band(item.assets["B05"].href, bounds, grid)
            b8a, _ = read_band(item.assets["B8A"].href, bounds, grid)
            b11, _ = read_band(item.assets["B11"].href, bounds, grid)
            scl, _ = read_band(item.assets["SCL"].href, bounds, grid, Resampling.nearest)
        except Exception as exc:  # one bad scene must not stop the cache
            print(f"  skip {day}: {exc}")
            continue
        ok = ~np.isin(scl.astype(int), list(SCL_BAD))
        if ok.mean() < 0.5:
            print(f"  skip {day}: {100 * (1 - ok.mean()):.0f}% cloud over field")
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            ndvi.append((b8 - b4) / (b8 + b4))
            ndre.append((b8a - b5) / (b8a + b5))
            ndmi.append((b8 - b11) / (b8 + b11))
        clear.append(ok)
        dates.append(day)
        print(f"  {day}  clear {100 * ok.mean():.0f}%")

    np.savez_compressed(out_dir / "s2_stack.npz", dates=np.array(dates), ndvi=np.array(ndvi, "float32"),
                        ndre=np.array(ndre, "float32"), ndmi=np.array(ndmi, "float32"), clear=np.array(clear))
    return grid


def fetch_terrain(bounds, grid: dict, out_dir: Path) -> None:
    catalog = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    item = next(catalog.search(collections=["cop-dem-glo-30"], bbox=bounds).items())
    elev, _ = read_band(item.assets["data"].href, bounds, grid)
    px = abs(grid["transform"].a)
    gy, gx = np.gradient(elev, px)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # relative elevation: below the 5x5 neighbourhood mean = where water collects
    pad = np.pad(elev, 2, mode="edge")
    local = np.mean([pad[i:i + elev.shape[0], j:j + elev.shape[1]] for i in range(5) for j in range(5)], axis=0)
    np.savez_compressed(out_dir / "terrain.npz", elevation=elev, slope=slope, rel_elev=elev - local)
    print(f"terrain: Copernicus DEM 30 m, elevation {elev.min():.0f}-{elev.max():.0f} m, max slope {slope.max():.1f} deg")


def fetch_soil(lon: float, lat: float, out_dir: Path) -> None:
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {"lon": lon, "lat": lat, "property": ["phh2o", "nitrogen", "soc", "clay"],
              "depth": "0-5cm", "value": "mean"}
    try:
        layers = requests.get(url, params=params, timeout=60).json()["properties"]["layers"]
    except Exception as exc:
        print(f"soilgrids unavailable ({exc}); soil prior will be neutral")
        return
    soil = {}
    for layer in layers:
        factor = layer["unit_measure"]["d_factor"]
        soil[layer["name"]] = {"value": layer["depths"][0]["values"]["mean"] / factor,
                               "unit": layer["unit_measure"]["target_units"]}
    soil["source"] = "SoilGrids 2.0 (ISRIC), 250 m, 0-5 cm"
    (out_dir / "soil.json").write_text(json.dumps(soil, indent=1), encoding="utf-8")
    print(f"soil: {soil}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-s2", action="store_true")
    args = ap.parse_args()

    field_id, hero, _ = prepare_field()
    minx, miny, maxx, maxy = shape(hero["geometry"]).bounds
    bounds = (minx - BUFFER_DEG, miny - BUFFER_DEG, maxx + BUFFER_DEG, maxy + BUFFER_DEG)
    out_dir = ROOT / "data" / "processed" / field_id
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"

    if args.skip_s2 and meta_path.exists():
        m = json.loads(meta_path.read_text())
        grid = {"crs": m["crs"], "transform": rasterio.Affine(*m["transform"]), "shape": tuple(m["shape"])}
    else:
        grid = fetch_s2(bounds, out_dir)
    meta_path.write_text(json.dumps({"field_id": field_id, "crs": grid["crs"], "transform": list(grid["transform"])[:6],
                                     "shape": list(grid["shape"]), "bounds_wgs84": bounds}, indent=1))
    fetch_terrain(bounds, grid, out_dir)
    c = shape(hero["geometry"]).centroid
    fetch_soil(c.x, c.y, out_dir)


if __name__ == "__main__":
    main()
