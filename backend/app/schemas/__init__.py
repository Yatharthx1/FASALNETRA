"""Pydantic v2 request/response schemas. Every route declares one as its response_model."""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.ivr import IVRRegisteredSimulateResponse


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


class TrackPoint(BaseModel):
    t: int = Field(description="phone time, ms since epoch")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy: float = Field(ge=0, le=5000, description="metres, 1 sigma")
    heading: float | None = Field(default=None, ge=0, le=360)
    speed: float | None = Field(default=None, ge=0, le=50)
    source: Literal["gps", "steps", "hold"] = "gps"


class TrackIn(BaseModel):
    points: list[TrackPoint] = Field(min_length=1, max_length=900, description="batched 5 Hz samples")


class TrackOut(BaseModel):
    stored: int
    total: int


class LocateIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy: float = Field(default=10.0, ge=0, le=5000)


class ParcelOut(BaseModel):
    khasra: str | None
    village_id: str | None
    area_ha: float | None
    recorded_crop: str | None


class LocateOut(BaseModel):
    status: Literal["on_field", "near_field", "away"]
    distance_m: float
    accuracy_m: float
    parcel: ParcelOut | None
    parcel_is_mapped_field: bool


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


class CallOut(BaseModel):
    case_id: int
    simulated: bool
    call_sid: str | None
    first_prompt: IVRRegisteredSimulateResponse


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
