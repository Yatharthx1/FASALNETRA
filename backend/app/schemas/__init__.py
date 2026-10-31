"""Pydantic v2 request/response schemas. Every route declares one as its response_model."""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FarmerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    village: str
    language: str


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    khasra: str
    crop: str
    sowing_date: date
    area_acres: float
    geometry: dict
    centroid_lat: float
    centroid_lon: float
    farmer: FarmerOut


class Driver(BaseModel):
    en: str
    hi: str


class CauseRisk(BaseModel):
    score: float
    band: Literal["safe", "watch", "high"]
    drivers: list[Driver]


class RiskDay(BaseModel):
    date: str
    das: int
    top: str
    score: float
    band: Literal["safe", "watch", "high"]
    causes: dict[str, CauseRisk]


class RiskOut(BaseModel):
    field_id: str
    mode: Literal["replay", "forecast"]
    rule_status: str
    days: list[RiskDay]


class GridCell(BaseModel):
    id: str
    polygon: dict
    centre: list[float]
    ndvi: float | None
    z_ndvi: float | None
    z_ndre: float | None
    z_ndmi: float | None
    low_spot: bool
    slope_deg: float | None
    flagged: bool


class ScanSummary(BaseModel):
    cells_in_field: int
    cells_flagged: int
    flagged_acres: float
    pattern: Literal["none", "patch", "scattered", "field_wide"]
    strength: float
    low_spot_overlap: float
    water_signal: float | None


class ScanOut(BaseModel):
    field_id: str
    scene_date: str
    cells: list[GridCell]
    summary: ScanSummary


class CaseCreate(BaseModel):
    field_id: str = "demo"


class KeypadIn(BaseModel):
    answers: dict[str, bool] = Field(description="answer id -> yes/no, e.g. whitefly_under_leaves")


class TrapsIn(BaseModel):
    counts: list[int] = Field(min_length=1, max_length=8)


class WalkIn(BaseModel):
    trail: list[tuple[float, float]] = Field(min_length=3, description="[lon, lat] GPS points around the patch")


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    spot: int
    cell_id: str | None
    lat: float | None
    lon: float | None
    vision: dict[str, Any]


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_id: str
    status: str
    created_at: datetime
    target_cells: list[dict]
    keypad: dict[str, bool]
    trap_counts: list[int]
    walk_trail: list
    zone: dict | None
    zone_acres: float | None
    evidence: dict | None
    photos: list[PhotoOut]


class LinkOut(BaseModel):
    case_id: int
    url: str
    sms_sent: bool
    simulated: bool


class IvrIn(BaseModel):
    step: str
    digit: str | None = None


class IvrOut(BaseModel):
    """What the farmer hears and which keys work; rendered as TwiML for Twilio or JSON for the web keypad."""
    case_id: int
    step: str
    say_hi: str
    audio: str | None = None
    options: dict[str, str] = Field(default_factory=dict)
    next_step: str | None = None
    hangup: bool = False


class CallOut(BaseModel):
    case_id: int
    simulated: bool
    call_sid: str | None
    first_prompt: IvrOut


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    status: str
    mode: str
    plan: dict
    route: dict
    window: dict
    schedule: list[dict]
    savings: dict
    ticket: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DidiProfileOut(BaseModel):
    name: str
    shg: str
    village: str
    drone: str
    batteries_ready: int
    tank_l: float
    base: list[float]
    jobs_open: int
    jobs_done: int
    acres_sprayed: float
    acres_saved: float
    pesticide_saved: float
    pesticide_unit: str


class JobAction(BaseModel):
    action: Literal["accept", "decline", "start", "verified", "rejected", "complete"]
    note: str | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    type: str
    case_id: int | None
    payload: dict
