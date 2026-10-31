from fastapi import APIRouter

from backend.app.api.v1.routes import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])

# Add routers here as the P0 slices are implemented:
# farmers, ivr, sms, risk, traps, field_walk, evidence, missions, events, demo.
