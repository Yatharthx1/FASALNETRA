"""Pest data sources: KCC surge calendar, GBIF / KCC seasonal priors, Kindwise photo answers, the surge outlook."""
import csv
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from backend.app.services import evidence
from backend.app.services.risk import pests, rules, seasonality, surge
from backend.app.services.vision import kindwise

REPO = Path(__file__).resolve().parents[3]


def _kcc_script():
    spec = importlib.util.spec_from_file_location("build_kcc_surges", REPO / "scripts" / "build_kcc_surges.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pest_files(tmp_path, monkeypatch):
    """Point seasonality at empty temp files; tests write what they need."""
    monkeypatch.setattr(seasonality, "GBIF_FILE", tmp_path / "gbif.json")
    monkeypatch.setattr(seasonality, "KCC_FILE", tmp_path / "kcc.json")
    seasonality.reload()
    yield tmp_path
    seasonality.reload()


# --- KCC: farmer questions -> surge calendar --------------------------------------------------------------------

def test_kcc_questions_are_sorted_into_pests_in_english_and_hindi():
    assert pests.kcc_cause("Soybean me safed makkhi aur peela pan") == "yellow_mosaic"
    assert pests.kcc_cause("control of girdle beetle in soybean") == "girdle_beetle"
    assert pests.kcc_cause("illi lag gayi hai patte kha rahi") == "chewing_damage"
    assert pests.kcc_cause("leaf rust spots") == "fungal"
    assert pests.kcc_cause("market rate of soybean") is None


def test_kcc_script_finds_the_week_farmers_call_most(tmp_path):
    rows = []
    for year in (2022, 2023):
        for day in range(1, 29):   # 28 whitefly questions in mid-August, each year
            rows.append({"Crop": "Soybean", "StateName": "MADHYA PRADESH", "DistrictName": "MANDSAUR",
                         "QueryText": "white fly control in soybean", "CreatedOn": f"{year}-08-{(day % 7) + 13:02d} 10:00:00"})
        rows.append({"Crop": "Soybean", "StateName": "MADHYA PRADESH", "DistrictName": "MANDSAUR",
                     "QueryText": "girdle beetle", "CreatedOn": f"{year}-07-25 09:00:00"})
        rows.append({"Crop": "Wheat", "StateName": "MADHYA PRADESH", "DistrictName": "MANDSAUR",
                     "QueryText": "white fly", "CreatedOn": f"{year}-08-14 09:00:00"})      # not soybean
        rows.append({"Crop": "Soybean", "StateName": "GUJARAT", "DistrictName": "SURAT",
                     "QueryText": "white fly", "CreatedOn": f"{year}-03-01 09:00:00"})      # other state
    f = tmp_path / "kcc.csv"
    with open(f, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    mod = _kcc_script()
    counts, stats, years = mod.read([f], "madhya pradesh", set())
    assert stats["yellow_mosaic"] == 56 and stats["girdle_beetle"] == 2 and years == {2022, 2023}
    cal = mod.calendar(counts, years)
    wm = cal["yellow_mosaic"]
    assert wm["peak_week"] == mod.week_of_year(date(2022, 8, 16)) == 32
    assert wm["peak_spread_weeks"] == 0.0              # same week both years: a steady calendar
    assert all(29 <= w <= 34 for w in wm["surge_weeks"])


def test_month_level_kcc_rows_are_placed_mid_month(tmp_path):
    f = tmp_path / "kcc.csv"
    f.write_text("Crop,State,Year,Month,Query\nSoybean,Madhya Pradesh,2024,Aug,yellow mosaic\n", encoding="utf-8")
    _, stats, _ = _kcc_script().read([f], "madhya pradesh", set())
    assert stats["yellow_mosaic"] == 1 and stats["no_date"] == 0


# --- seasonal priors --------------------------------------------------------------------------------------------

def test_kcc_calendar_is_preferred_over_gbif(pest_files):
    weekly = [0.0] * 53
    weekly[32] = 10.0
    (pest_files / "kcc.json").write_text(json.dumps({"years": [2023], "causes": {"yellow_mosaic": {
        "total": 10, "weekly_mean": weekly, "peak_week": 32, "surge_weeks": [32]}}}))
    (pest_files / "gbif.json").write_text(json.dumps({"causes": {"yellow_mosaic": {"Bemisia tabaci": {
        "india_by_month": [100] * 12, "malwa_total": 5}}}}))
    seasonality.reload()
    p, source = seasonality.prior("yellow_mosaic", date(2025, 8, 15))
    assert source == "kcc" and p == 1.0
    assert seasonality.calendar()["yellow_mosaic"]["source"] == "kcc"


def test_a_pest_seen_all_year_is_not_in_season(pest_files):
    (pest_files / "gbif.json").write_text(json.dumps({"causes": {"chewing_damage": {"Spodoptera litura": {
        "india_by_month": [80] * 12, "malwa_total": 7}}}}))
    seasonality.reload()
    assert seasonality.in_season("chewing_damage", date(2025, 8, 15)) == 0.0
    assert "chewing_damage" not in seasonality.season_vote(date(2025, 8, 15))


def test_too_few_gbif_records_give_no_prior(pest_files):
    (pest_files / "gbif.json").write_text(json.dumps({"causes": {"fungal": {"Phakopsora pachyrhizi": {
        "india_by_month": [2] * 12, "malwa_total": 0}}}}))
    seasonality.reload()
    assert seasonality.prior("fungal", date(2025, 8, 15)) == (None, None)


# --- Kindwise crop.health / plant.id ----------------------------------------------------------------------------

@pytest.mark.parametrize("name,label", [
    ("Soybean mosaic virus", "yellow_mosaic"), ("Mungbean yellow mosaic India virus Begomovirus", "yellow_mosaic"),
    ("Soybean rust Phakopsora pachyrhizi", "fungal"), ("Tobacco cutworm Spodoptera litura", "chewing_damage"),
    ("Girdle beetle Obereopsis brevis", "girdle_beetle"), ("Nitrogen deficiency", "uniform_yellowing"),
    ("Noctuidae", "chewing_damage"), ("Erebidae", "chewing_damage"), ("Aleyrodidae", "yellow_mosaic"),
    ("Colletotrichum", "fungal"), ("healthy", "healthy"), ("Hail damage", "unsure"),
])
def test_kindwise_names_map_onto_our_labels(name, label):
    assert kindwise.label_for(name) == label


def test_kindwise_answer_adds_up_names_with_the_same_label():
    resp = {"result": {"crop": {"suggestions": [{"name": "soybean", "scientific_name": "Glycine max"}]},
                       "disease": {"suggestions": [{"name": "Frogeye leaf spot", "probability": 0.4},
                                                   {"name": "Soybean rust", "probability": 0.3},
                                                   {"name": "Soybean mosaic virus", "probability": 0.2}]}}}
    out = kindwise.parse(resp)
    assert out["label"] == "fungal" and out["confidence"] == 0.7 and out["is_soybean"] is True


def test_kindwise_is_skipped_without_a_key(monkeypatch):
    monkeypatch.delenv("KINDWISE_API_KEY", raising=False)
    assert not kindwise.available() and kindwise.classify(b"x") is None


# --- evidence + surge outlook -----------------------------------------------------------------------------------

def test_season_and_expert_photo_vote_but_season_is_never_an_observation():
    e = evidence.build(season={"yellow_mosaic": 0.9}, weather_scores={"yellow_mosaic": 0.95, "fungal": 0.3},
                       das=40, advisory_flags={"yellow_mosaic": True})
    assert e["level"] != "high"                      # priors + weather alone: never high
    e = evidence.build(photo_expert={"label": "yellow_mosaic", "confidence": 0.9}, season={"yellow_mosaic": 0.9})
    assert "photo_expert" in e["agreeing_signals"] and "season" in e["agreeing_signals"]


def _day(d: str, scores: dict[str, float]) -> dict:
    return {"date": d, "causes": {c: {"score": s, "band": rules.band(s), "drivers": [{"en": "x", "hi": "x"}]}
                                  for c, s in scores.items()}}


def test_surge_outlook_finds_onset_and_peak_and_needs_kcc_for_high_confidence(pest_files):
    base = {c: 10.0 for c in rules.SCORERS}
    days = [_day("2025-08-15", base), _day("2025-08-16", {**base, "fungal": 75.0}),
            _day("2025-08-17", {**base, "fungal": 90.0})]
    out = surge.outlook(days, date(2025, 8, 15))
    top = out["pests"][0]
    assert top["cause"] == "fungal" and top["onset_date"] == "2025-08-16" and top["peak_date"] == "2025-08-17"
    assert top["confidence"] == "low"                 # no seasonal data at all
    assert out["next_update"] == "2025-08-20"

    weekly = [0.0] * 53
    weekly[32] = 5.0
    (pest_files / "kcc.json").write_text(json.dumps({"years": [2023], "causes": {"fungal": {
        "total": 5, "weekly_mean": weekly, "peak_week": 32, "surge_weeks": [32]}}}))
    seasonality.reload()
    top = surge.outlook(days, date(2025, 8, 15))["pests"][0]
    assert top["confidence"] == "high" and "Kisan Call Centre questions" in top["basis"]
