import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from backend.app.api.deps import FieldDep
from backend.app.api.v1.routes.ivr import execute_missed_call_callback
from backend.app.db.session import SessionLocal as IvrSessionLocal
from backend.app.schemas import FieldOut, RiskOut, ScanOut
from backend.app.services import fields

router = APIRouter(prefix="/fields")


@router.get("/{field_id}", response_model=FieldOut)
async def get_field(field: FieldDep) -> FieldOut:
    return field


@router.get("/{field_id}/risk", response_model=RiskOut)
async def get_risk(field: FieldDep) -> RiskOut:
    """15 daily risk scores from today (demo: replay of the 2025 season from 15 Aug)."""
    return await asyncio.to_thread(fields.risk, field)


@router.get("/{field_id}/surge")
async def get_surge(field: FieldDep) -> dict:
    """Next surge per pest: 15-day weather risk x how in season it is (Kisan Call Centre calls, else GBIF)."""
    return await asyncio.to_thread(fields.surge_outlook, field)


@router.get("/{field_id}/spray-window")
async def get_spray_window(field: FieldDep) -> dict:
    """Spray window feasibility, wind speed drift risk, and recommended spray slot."""
    return await asyncio.to_thread(fields.spray_window, field)


@router.get("/{field_id}/combined-advisory")
async def get_combined_advisory(field: FieldDep) -> dict:
    """Fused Sentinel-2 satellite anomaly and agrometeorological advisory score."""
    try:
        return await asyncio.to_thread(fields.combined_advisory, field)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Satellite or weather data missing: {exc}") from exc


@router.get("/{field_id}/soybean-profile")
async def get_soybean_profile(field: FieldDep) -> dict:
    """Specialized ICAR-IISR soybean phenological stage, ETL thresholds, and nutrition profile."""
    return await asyncio.to_thread(fields.soybean_profile, field)


@router.post("/{field_id}/missed-call")
async def missed_call(field: FieldDep, background_tasks: BackgroundTasks) -> dict[str, str | int]:
    """Dashboard stand-in for the farmer giving a missed call: same free callback as POST /ivr/webhook."""
    background_tasks.add_task(execute_missed_call_callback, field.farmer.phone, IvrSessionLocal)
    return {"phone": field.farmer.phone, "callback_in_s": 3}


@router.get("/{field_id}/demo-walk", response_model=list[tuple[float, float]])
async def demo_walk(field: FieldDep) -> list[tuple[float, float]]:
    """PRD fallback when GPS drifts indoors: a pre-recorded walk around the satellite-flagged patch."""
    return await asyncio.to_thread(fields.demo_walk, field)


@router.get("/{field_id}/scan", response_model=ScanOut)
async def get_scan(field: FieldDep) -> ScanOut:
    """Sentinel-2 10 m grid cells for the field, with weak cells flagged."""
    try:
        return await asyncio.to_thread(fields.scan, field)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Satellite cache missing; run scripts/fetch_field_data.py ({exc})") from exc
