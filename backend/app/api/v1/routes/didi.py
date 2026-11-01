from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.app.api.deps import DbDep
from backend.app.core.config import settings
from backend.app.db.models import DidiJob
from backend.app.schemas import DidiProfileOut, JobAction, JobOut
from backend.app.services import didi
from backend.app.services.events import emit

router = APIRouter(prefix="/didi")

# action -> (allowed from statuses, new status)
TRANSITIONS = {
    "accept": ({"new"}, "accepted"),
    "decline": ({"new"}, "declined"),
    "verified": ({"accepted"}, "accepted"),      # verify_then_spray: Didi saw the damage herself
    "rejected": ({"accepted"}, "done"),          # verify_then_spray: nothing to spray
    "start": ({"accepted"}, "flying"),
    "complete": ({"accepted", "flying"}, "done"),
}
URGENCY = {"spray": 0, "verify_then_spray": 1}


def _out(job: DidiJob) -> JobOut:
    out = JobOut.model_validate(job)
    out.ticket = didi.ticket(job)
    return out


@router.get("/profile", response_model=DidiProfileOut)
async def profile(db: DbDep) -> DidiProfileOut:
    jobs = (await db.execute(select(DidiJob))).scalars().all()
    done = [j for j in jobs if j.status == "done"]
    units = {j.savings.get("pesticide", {}).get("unit") for j in done} - {None}
    return DidiProfileOut(
        **didi.profile(),
        jobs_open=sum(j.status in ("new", "accepted", "flying") for j in jobs),
        jobs_done=len(done),
        acres_sprayed=round(sum(j.plan.get("zone_acres", 0) for j in done), 2),
        acres_saved=round(sum(j.savings.get("acres_not_sprayed", 0) for j in done), 2),
        pesticide_saved=round(sum(j.savings.get("pesticide", {}).get("saved", 0) for j in done), 1),
        pesticide_unit=units.pop() if len(units) == 1 else "ml",
    )


async def _job(db, job_id: int) -> DidiJob:
    job = await db.get(DidiJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Job {job_id} not found")
    return job


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(db: DbDep) -> list[JobOut]:
    jobs = (await db.execute(select(DidiJob).order_by(DidiJob.id))).scalars().all()
    open_first = sorted(jobs, key=lambda j: (j.status in ("done", "declined"), URGENCY.get(j.mode, 2), j.id))
    return [_out(j) for j in open_first]


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: DbDep) -> JobOut:
    return _out(await _job(db, job_id))


@router.post("/jobs/{job_id}", response_model=JobOut)
async def act(job_id: int, payload: JobAction, db: DbDep) -> JobOut:
    job = await _job(db, job_id)
    allowed, new = TRANSITIONS[payload.action]
    if job.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot {payload.action} a job that is {job.status}")
    if payload.action == "start" and job.mode == "verify_then_spray" and not job.window.get("verified"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Verify the damage in the field before spraying")
    job.status = new
    if payload.action == "verified":
        job.window = {**job.window, "verified": True}
    job.case.status = {"accepted": "didi_accepted", "flying": "spraying", "done": "closed",
                       "declined": "didi_declined"}.get(new, job.case.status)
    await db.commit()
    await db.refresh(job)
    extra = {}
    if payload.action == "complete":
        s = job.savings
        extra = {"acres_not_sprayed": s.get("acres_not_sprayed"), "chemical_saved": s.get("pesticide", {}).get("saved"),
                 "unit": s.get("pesticide", {}).get("unit"), "battery_saved": s.get("battery", {}).get("saved"),
                 "fuel_saved_l": s.get("fuel_l", {}).get("saved")}
    await emit(db, f"didi_{payload.action}", job.case_id, job=job.id, note=payload.note, **extra)
    return _out(job)


@router.get("/jobs/{job_id}/waypoints")
async def waypoints(job_id: int, db: DbDep) -> FileResponse:
    await _job(db, job_id)
    path = settings.waypoints_dir / f"job_{job_id}.waypoints"
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Waypoints not generated")
    return FileResponse(path, media_type="text/plain", filename=path.name)
