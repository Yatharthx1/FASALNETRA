from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String

from backend.app.db.session import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), default="Kisan", nullable=False)
    language = Column(String(10), default="hi", nullable=False)

    # Onboarding details gathered via IVR
    crop = Column(String(50), nullable=True)
    sowing_date_bracket = Column(String(50), nullable=True)
    pincode = Column(String(10), nullable=True)
    village = Column(String(100), nullable=True)
    corner_landmark = Column(String(50), nullable=True)
    neighbor_crop = Column(String(50), nullable=True)
    grassy_border = Column(String(10), nullable=True)

    status = Column(String(30), default="onboarding", nullable=False)  # onboarding | registered
    active_flow = Column(String(30), default="safe", nullable=False)    # safe | warning | result | followup
    risk_score = Column(Integer, default=20, nullable=True)
    spray_booked = Column(String(10), default="no", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
