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
