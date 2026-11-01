from fastapi import APIRouter

from backend.app.api.v1.routes import cases, didi, events, fields, health, ivr, whatsapp

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(fields.router, tags=["fields"])
api_router.include_router(cases.router, tags=["cases"])
api_router.include_router(ivr.router)
api_router.include_router(whatsapp.router)
api_router.include_router(didi.router, tags=["drone-didi"])
api_router.include_router(events.router, tags=["events"])
