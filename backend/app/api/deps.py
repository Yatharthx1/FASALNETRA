from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.database import get_db
from backend.app.db.models import Case, Field
from backend.app.services import cases, fields

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_field(field_id: str, db: DbDep) -> Field:
    try:
        return await fields.get_field(db, field_id)
    except fields.FieldNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Field {field_id} not found") from None


async def get_case(case_id: int, db: DbDep) -> Case:
    try:
        return await cases.get_case(db, case_id)
    except cases.CaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found") from None


FieldDep = Annotated[Field, Depends(get_field)]
CaseDep = Annotated[Case, Depends(get_case)]
