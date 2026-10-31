"""Grid targets from the blurry Sentinel-2 grid, the onboarding field-profile prior and the photo advice lookup."""
import pytest

from backend.app.services import evidence, vision
from backend.app.services.mapping import targets

# A 6 x 6 grid of 10 m cells near Mandsaur; one cell is ~0.00009 deg
D = 0.00009
LON0, LAT0 = 75.11, 24.10
FIELD = {"type": "Polygon", "coordinates": [[[LON0, LAT0], [LON0 + 6 * D, LAT0], [LON0 + 6 * D, LAT0 + 6 * D],
                                              [LON0, LAT0 + 6 * D], [LON0, LAT0]]]}


def _cell(r: int, c: int, z: float = 0.0, flagged: bool = False, low: bool = False) -> dict:
    x, y = LON0 + c * D, LAT0 + r * D
    poly = {"type": "Polygon", "coordinates": [[[x, y], [x + D, y], [x + D, y + D], [x, y + D], [x, y]]]}
    return {"id": f"r{r}c{c}", "polygon": poly, "centre": [x + D / 2, y + D / 2], "z_ndvi": z, "z_ndre": z,
            "low_spot": low, "flagged": flagged}


def _grid(flags: dict[tuple[int, int], float] = (), low: set = frozenset()) -> list[dict]:
    flags = dict(flags)
    return [_cell(r, c, flags.get((r, c), 0.0), (r, c) in flags, (r, c) in low) for r in range(6) for c in range(6)]


def test_adjacent_flagged_cells_become_one_patch_with_one_stop():
    cells = _grid({(1, 1): -2.0, (1, 2): -2.5, (2, 2): -1.8})
    assert len(targets.patches(cells)) == 1
    stops = targets.pick(cells, FIELD)
    assert [s["id"] for s in stops] == ["r1c2"]           # the weakest cell of the patch
    assert stops[0]["reason"] == "satellite_patch" and stops[0]["patch_cells"] == 3


def test_big_patch_gets_a_second_stop_at_its_far_end():
    cells = _grid({(0, 0): -2.0, (0, 1): -2.0, (1, 1): -2.0, (2, 2): -2.0, (3, 3): -3.0})
    stops = targets.pick(cells, FIELD)
    assert {s["reason"] for s in stops} == {"satellite_patch", "patch_edge"}
    assert {s["id"] for s in stops} == {"r3c3", "r0c0"}


def test_stops_closer_than_gps_can_tell_are_dropped():
    cells = _grid({(1, 1): -2.0, (3, 1): -2.0})   # two patches, 20 m apart -> both kept
    assert len(targets.pick(cells, FIELD)) == 2
    cells = _grid({(1, 1): -2.0, (1, 3): -2.0, (5, 5): -2.0})
    assert len(targets.pick(cells, FIELD, n=2)) == 2


def test_no_satellite_flag_still_gives_a_walk_led_by_the_field_profile():
    cells = _grid({(3, 3): -0.2})
    for c in cells:
        c["flagged"] = False
    plain = targets.pick(cells, FIELD)
    assert plain and plain[0]["reason"] == "weakest"
    grassy = targets.pick(cells, FIELD, {"grassy_border": "yes"})
    assert "border" in {s["reason"] for s in grassy}


def test_route_starts_at_the_field_corner():
    cells = _grid({(5, 5): -3.0, (0, 0): -2.0})
    assert [s["id"] for s in targets.pick(cells, FIELD)] == ["r0c0", "r5c5"]


def test_field_profile_is_a_prior_that_never_makes_high_alone():
    e = evidence.build(field_profile={"neighbor_crop": "urad_moong", "grassy_border": "yes"}, das=40)
    assert e["cause"] == "yellow_mosaic" and e["level"] != "high"
    assert any(s["name"] == "field_profile" for s in e["signals"])


def test_girdle_beetle_photo_is_a_pest_cause_with_a_table_dose():
    e = evidence.build(photo_ai={"label": "girdle_beetle", "confidence": 0.9, "quality": {"ok": True}}, zone_acres=0.3)
    assert e["cause"] == "girdle_beetle" and e["plan"]["spray"] is not None


@pytest.mark.parametrize("label,pesticide", [("yellow_mosaic", True), ("girdle_beetle", True),
                                             ("uniform_yellowing", False)])
def test_photo_advice_comes_from_the_icar_table(label, pesticide):
    a = vision.advice(label)
    assert a["pesticide"] is pesticide
    assert (a["product"] is not None) is pesticide


def test_healthy_or_unsure_photo_gets_no_advice():
    assert vision.advice("healthy") is None and vision.advice("unsure") is None


def test_provider_defaults(monkeypatch):
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert vision.provider() == "local"
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert vision.provider() == "gemini"
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    assert vision.provider() == "mock"


def test_aws_sms_sends_dlt_ids_for_india_and_never_raises(monkeypatch):
    import boto3
    from botocore.exceptions import ClientError

    from backend.app.core.config import settings
    from backend.app.services import communications

    sent = {}

    class Fake:
        def send_text_message(self, **kw):
            sent.update(kw)
            if kw["DestinationPhoneNumber"].endswith("0"):
                raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "sandbox"}}, "SendTextMessage")
            return {"MessageId": "m-1"}

    monkeypatch.setattr(boto3, "client", lambda *a, **k: Fake())
    for k, v in {"sms_provider": "aws", "aws_sms_sender_id": "FSLNTR", "aws_sms_entity_id": "E1",
                 "aws_sms_template_id": "T1"}.items():
        monkeypatch.setattr(settings, k, v)
    ok = communications.send_sms("+919876543211", "link")
    assert ok.sid == "m-1" and ok.error is None
    assert sent["DestinationCountryParameters"] == {"IN_ENTITY_ID": "E1", "IN_TEMPLATE_ID": "T1"}
    assert sent["OriginationIdentity"] == "FSLNTR"
    failed = communications.send_sms("+919876543210", "link")
    assert failed.sid is None and "sandbox" in failed.error


def test_whatsapp_channel_uses_the_sandbox_sender_and_the_call_says_whatsapp(monkeypatch):
    from backend.app.core.config import settings
    from backend.app.services import communications
    from backend.app.services.communications.registered_state_machine import get_registered_flow_config

    sent = {}

    class Msgs:
        def create(self, **kw):
            sent.update(kw)
            return type("M", (), {"sid": "SM1"})()

    monkeypatch.setattr(settings, "sms_provider", "whatsapp")
    monkeypatch.setattr(communications, "_client", lambda: type("C", (), {"messages": Msgs()})())
    assert communications.send_sms("+919876543211", "link").sid == "SM1"
    assert sent["to"] == "whatsapp:+919876543211" and sent["from_"] == f"whatsapp:{settings.twilio_whatsapp_from}"
    assert "व्हाट्सऐप" in get_registered_flow_config("report", "sms_dispatched")["prompt_text"]


def test_small_wide_leaf_crop_is_not_judged_blurry_by_stretching():
    """Phone crops are small and wide (e.g. 502 x 251); scoring them stretched to 512 x 512 failed sharp photos."""
    import numpy as np
    from PIL import Image, ImageDraw

    rng = np.random.default_rng(5)
    img = Image.new("RGB", (502, 251), (70, 130, 50))
    d = ImageDraw.Draw(img)
    for _ in range(120):
        x, y, r = int(rng.integers(0, 502)), int(rng.integers(0, 251)), int(rng.integers(2, 9))
        d.ellipse([x, y, x + r, y + r // 2 + 1], fill=(120, 160, 60))   # faint mottling
    q = vision.quality(img)
    assert q["ok"], q   # stretched to 512 x 512 this scored ~17 and was sent back as "blurry"
