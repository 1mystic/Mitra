from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.db import Application
from ..models.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

VALID_STATUSES = {"wishlist", "applied", "interview", "offered", "rejected", "withdrawn"}


@router.get("/{user_id}", response_model=list[ApplicationRead])
async def list_applications(user_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Application).where(Application.user_id == user_id).order_by(Application.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ApplicationRead, status_code=201)
async def create_application(body: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUSES}")
    app = Application(**body.model_dump())
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.patch("/{app_id}", response_model=ApplicationRead)
async def update_application(app_id: str, body: ApplicationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if body.status and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUSES}")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(app, field, value)
    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
async def delete_application(app_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(app)
    await db.commit()
