"""Drone Didi schedule and savings rules."""
from datetime import date

import pytest
from shapely.geometry import Polygon, mapping

from backend.app.services import didi, missions

WINDOW = {"date": "2025-08-16", "best": "2025-08-16T06:00", "slots": []}


def test_spray_ticket_gets_check_after_three_days_and_advisory_repeat():
    s = didi.schedule("yellow_mosaic", "spray", WINDOW, date(2025, 8, 15))
    assert [(x["date"], x["time"], x["kind"]) for x in s] == [
        ("2025-08-16", "06:00", "spray"), ("2025-08-19", "07:00", "check"), ("2025-08-26", "06:00", "repeat_spray")]


def test_no_repeat_spray_when_advisory_gives_none():
    kinds = [x["kind"] for x in didi.schedule("girdle_beetle", "verify_then_spray", WINDOW, date(2025, 8, 15))]
    assert kinds == ["verify_then_spray", "check"]


def test_first_visit_falls_back_to_morning_without_a_safe_slot():
    s = didi.schedule("fungal", "spray", {"date": "2025-08-16", "best": None, "slots": []}, date(2025, 8, 15))
    assert (s[0]["date"], s[0]["time"]) == ("2025-08-16", "06:00")


@pytest.fixture
def field_and_zone():
    lon, lat, d = 75.1218, 24.1030, 0.0006
    field = mapping(Polygon([(lon, lat), (lon + d, lat), (lon + d, lat + 2 * d), (lon, lat + 2 * d)]))
    zone = mapping(Polygon([(lon, lat), (lon + d / 2, lat), (lon + d / 2, lat + d / 2), (lon, lat + d / 2)]))
    return field, zone


def test_zone_only_spray_saves_against_whole_field(field_and_zone):
    field, zone = field_and_zone
    route = missions.plan_route(zone, 4, 1, 3)
    s = didi.savings(field, zone, "yellow_mosaic", route)
    assert s["pesticide"]["saved"] > s["pesticide"]["used"] > 0
    assert s["water_l"]["saved"] > 0 and s["flight_min"]["saved"] > 0
    assert s["battery"]["saved"] >= 0 and s["fuel_l"]["saved"] >= 0
    assert s["acres_not_sprayed"] > 0


def test_non_pest_cause_saves_no_pesticide_figure(field_and_zone):
    field, zone = field_and_zone
    s = didi.savings(field, zone, "water_stress", missions.plan_route(zone, 4, 1, 3))
    assert s["pesticide"] == {"saved": 0.0, "used": 0.0, "unit": None}
