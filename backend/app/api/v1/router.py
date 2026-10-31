from fastapi import APIRouter

from backend.app.api.v1.routes import health, ivr

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(ivr.router)

# Add routers here as the P0 slices are implemented:
# farmers, ivr, sms, risk, traps, field_walk, evidence, missions, events, demo.
