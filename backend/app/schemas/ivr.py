from typing import Any
from pydantic import BaseModel, Field


class IVRSimulateRequest(BaseModel):
    phone: str = Field(default="+919876543210", description="Farmer phone number")
    digits: str | None = Field(default=None, description="Keypad digit(s) entered")
    reset: bool = Field(default=False, description="Reset existing onboarding session")


class IVRStepOption(BaseModel):
    digit: str
    label: str


class IVRSimulateResponse(BaseModel):
    call_sid: str
    phone: str
    current_step: str
    prompt_id: str
    prompt_text: str
    num_digits: int
    options: list[IVRStepOption]
    answers: dict[str, Any]
    is_completed: bool
    reprompt_count: int
    message: str


class IVRRegisteredSimulateRequest(BaseModel):
    phone: str = Field(default="+919876543210", description="Farmer phone number")
    digits: str | None = Field(default=None, description="Keypad digit; omit to just read the current prompt")


class IVRRegisteredSimulateResponse(BaseModel):
    phone: str
    flow: str
    current_step: str
    prompt_id: str
    prompt_text: str
    valid_digits: list[str]
    is_completed: bool
    message: str
