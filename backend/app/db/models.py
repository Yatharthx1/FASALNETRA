from datetime import date, datetime, timezone

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FieldOwner(Base):
    """Owner of a mapped field. The IVR farmer registry (onboarding answers) is models/farmer.py, joined by phone."""
    __tablename__ = "field_owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    language: Mapped[str] = mapped_column(String(10), default="hi")
    village: Mapped[str] = mapped_column(String(80))


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("field_owners.id"))
    khasra: Mapped[str] = mapped_column(String(20))
    crop: Mapped[str] = mapped_column(String(30), default="soybean")
    sowing_date: Mapped[date] = mapped_column(Date)
    area_acres: Mapped[float] = mapped_column(Float)
    geometry: Mapped[dict] = mapped_column(JSON)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)

    farmer: Mapped[FieldOwner] = relationship(lazy="joined")


class Case(Base):
    """One problem report on one field: from the warning call to the finished spray."""
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id"))
    status: Mapped[str] = mapped_column(String(30), default="warned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    target_cells: Mapped[list] = mapped_column(JSON, default=list)   # satellite cells the farmer is asked to visit
    keypad: Mapped[dict] = mapped_column(JSON, default=dict)
    trap_counts: Mapped[list] = mapped_column(JSON, default=list)
    walk_trail: Mapped[list] = mapped_column(JSON, default=list)
    zone: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    zone_acres: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    field: Mapped[Field] = relationship(lazy="joined")
    photos: Mapped[list["Photo"]] = relationship(lazy="selectin", order_by="Photo.id")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String(20))          # leaf_top | leaf_under | chewed | trap
    spot: Mapped[int] = mapped_column(Integer, default=0)
    cell_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    path: Mapped[str] = mapped_column(String(200))
    vision: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DidiJob(Base):
    __tablename__ = "didi_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    status: Mapped[str] = mapped_column(String(20), default="new")   # new|verify|accepted|flying|done|declined
    mode: Mapped[str] = mapped_column(String(20))                    # spray | verify_then_spray
    plan: Mapped[dict] = mapped_column(JSON)
    route: Mapped[dict] = mapped_column(JSON)
    window: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule: Mapped[list] = mapped_column(JSON, default=list)
    savings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    case: Mapped[Case] = relationship(lazy="joined")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    type: Mapped[str] = mapped_column(String(40))
    case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class GpsFix(Base):
    """Phone position samples from the walk page: real GPS fixes and the 5 Hz fused track between them."""
    __tablename__ = "gps_fixes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    t_ms: Mapped[int] = mapped_column(BigInteger)                  # phone clock, ms since epoch (> 32 bit)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8))                 # gps | steps | hold
