"""Kisan Call Centre questions (AIKosh) -> when soybean farmers call about each pest: the surge calendar.

Download "Kisan Call Centre (KCC) - Transcripts of farmers queries and answers" from AIKosh (login needed) as
CSV, one or more files, then:

    python scripts/build_kcc_surges.py data/raw/kcc/*.csv
    python scripts/build_kcc_surges.py data/raw/kcc/*.csv --state "madhya pradesh" --districts mandsaur,neemuch,ratlam,ujjain

Column names are matched loosely (QueryText / query_text / Query, CreatedOn / created_on / Year + Month, ...).
Rows: soybean only, in the state (and districts) given; each question is put under one pest by keywords
(backend/app/services/risk/pests.py, English and Hindi in Latin script). Output, read by the app:
data/processed/pests/kcc_soybean.json with, per pest, questions per week of year (mean over years), the peak
week, the surge window (weeks at >= half the peak) and each year's peak week (how steady the timing is).
"""
import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.risk.pests import PESTS, kcc_cause

OUT = ROOT / "data" / "processed" / "pests" / "kcc_soybean.json"
WEEKS = 53
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y", "%d/%m/%Y",
                "%m/%d/%Y", "%d/%m/%Y %H:%M", "%Y/%m/%d")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

csv.field_size_limit(1 << 24)


def _col(header: list[str], *names: str) -> str | None:
    norm = {re.sub(r"[^a-z]", "", h.lower()): h for h in header}
    for n in names:
        if n in norm:
            return norm[n]
    return None


def _date(row: dict, cols: dict) -> date | None:
    raw = (row.get(cols["created"]) or "").strip() if cols["created"] else ""
    if raw:
        raw = raw.split(".")[0].replace("Z", "")
        for f in DATE_FORMATS:
            try:
                return datetime.strptime(raw, f).date()
            except ValueError:
                continue
    if cols["year"] and cols["month"]:
        try:
            y = int(float(row[cols["year"]]))
            m = str(row[cols["month"]]).strip().lower()
            mo = int(float(m)) if m.replace(".", "").isdigit() else MONTHS.get(m[:3])
            return date(y, mo, 15) if mo else None    # month-level data: middle of the month
        except (TypeError, ValueError):
            return None
    return None


def week_of_year(d: date) -> int:
    return min(WEEKS - 1, (d.timetuple().tm_yday - 1) // 7)


def read(paths: list[Path], state: str | None, districts: set[str]) -> tuple[dict, Counter, set[int]]:
    """counts[cause][year][week] -> questions; also how many rows were kept / skipped and why."""
    counts: dict = defaultdict(lambda: defaultdict(Counter))
    stats, years = Counter(), set()
    for path in paths:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            h = reader.fieldnames or []
            cols = {"crop": _col(h, "crop", "cropname"), "text": _col(h, "querytext", "query", "questions", "question"),
                    "type": _col(h, "querytype", "category"), "state": _col(h, "statename", "state"),
                    "district": _col(h, "districtname", "district"), "created": _col(h, "createdon", "date", "querydate"),
                    "year": _col(h, "year"), "month": _col(h, "month")}
            if not cols["text"]:
                sys.exit(f"{path}: no query text column in {h}")
            for row in reader:
                stats["rows"] += 1
                crop = (row.get(cols["crop"]) or "") if cols["crop"] else row.get(cols["text"], "")
                if "soy" not in crop.lower():
                    continue
                if state and cols["state"] and state not in (row.get(cols["state"]) or "").lower():
                    continue
                if districts and cols["district"] and (row.get(cols["district"]) or "").strip().lower() not in districts:
                    continue
                stats["soybean"] += 1
                d = _date(row, cols)
                if d is None:
                    stats["no_date"] += 1
                    continue
                text = f"{row.get(cols['text'], '')} {row.get(cols['type'], '') if cols['type'] else ''}"
                cause = kcc_cause(text)
                if cause is None:
                    continue
                stats[cause] += 1
                counts[cause][d.year][week_of_year(d)] += 1
                years.add(d.year)
    return counts, stats, years


def calendar(counts: dict, years: set[int]) -> dict:
    out = {}
    n_years = max(1, len(years))
    for cause in PESTS:
        by_year = counts.get(cause, {})
        weekly = [sum(by_year[y][w] for y in by_year) / n_years for w in range(WEEKS)]
        total = sum(sum(c.values()) for c in by_year.values())
        if not total:
            continue
        peak = max(range(WEEKS), key=lambda w: weekly[w])
        surge = [w for w in range(WEEKS) if weekly[w] >= 0.5 * weekly[peak]]
        yearly_peaks = {y: max(range(WEEKS), key=lambda w: c[w]) for y, c in by_year.items() if sum(c.values()) >= 5}
        out[cause] = {
            "total": total,
            "weekly_mean": [round(x, 2) for x in weekly],
            "peak_week": peak,
            "peak_dates": f"{_week_start(peak)} to {_week_start(peak + 1)}",
            "surge_weeks": surge,
            "peak_week_by_year": yearly_peaks,
            # small spread = farmers call at the same time every year = a calendar worth trusting
            "peak_spread_weeks": round(statistics.pstdev(yearly_peaks.values()), 1) if len(yearly_peaks) > 1 else None,
        }
    return out


def _week_start(w: int) -> str:
    return date.fromordinal(date(2025, 1, 1).toordinal() + 7 * min(w, WEEKS)).strftime("%d %b")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--state", default="madhya pradesh", help="state name filter, lower case ('' for all)")
    ap.add_argument("--districts", default="", help="comma-separated district names, lower case")
    args = ap.parse_args()

    districts = {d.strip().lower() for d in args.districts.split(",") if d.strip()}
    counts, stats, years = read(args.csv, args.state.lower() or None, districts)
    print(f"rows {stats['rows']}, soybean {stats['soybean']}, no date {stats['no_date']}, years {sorted(years)}")
    print("questions by pest:", {c: stats[c] for c in PESTS})
    cal = calendar(counts, years)
    for cause, c in cal.items():
        print(f"  {cause:15s} peak week {c['peak_week']:2d} ({c['peak_dates']}), surge weeks {c['surge_weeks'][:1]}..{c['surge_weeks'][-1:]}"
              f", spread across years {c['peak_spread_weeks']} weeks")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "Kisan Call Centre transcripts (AIKosh)", "state": args.state,
                               "districts": sorted(districts), "years": sorted(years), "causes": cal}, indent=2),
                   encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
