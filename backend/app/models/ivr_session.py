from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, JSON, String

from backend.app.db.session import Base


class IVRSession(Base):
    __tablename__ = "ivr_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    call_sid = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), index=True, nullable=False)
    flow = Column(String(50), default="onboarding", nullable=False)
    current_step = Column(String(50), default="welcome", nullable=False)
    reprompt_count = Column(Integer, default=0, nullable=False)
    answers = Column(JSON, default=dict, nullable=False)
    status = Column(String(30), default="in_progress", nullable=False)  # in_progress | completed | failed

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
