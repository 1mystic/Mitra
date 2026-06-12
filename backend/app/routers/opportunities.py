from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.db import Opportunity
from ..models.schemas import OpportunityCreate, OpportunityRead
from ..services import embedding_service

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityRead])
async def list_opportunities(
    type: str | None = Query(None),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Opportunity).where(Opportunity.is_active == True)
    if type:
        stmt = stmt.where(Opportunity.type == type)
    stmt = stmt.order_by(Opportunity.fetched_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/search", response_model=list[OpportunityRead])
async def search_opportunities(
    query: str,
    limit: int = Query(10, le=20),
    db: AsyncSession = Depends(get_db),
):
    embedding = await embedding_service.embed(query)
    stmt = (
        select(Opportunity)
        .where(Opportunity.is_active == True)
        .where(Opportunity.embedding.isnot(None))
        .order_by(Opportunity.embedding.cosine_distance(embedding))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=OpportunityRead, status_code=201)
async def add_opportunity(body: OpportunityCreate, db: AsyncSession = Depends(get_db)):
    embed_text = f"{body.title} {body.company} {' '.join(body.required_skills)} {body.description or ''}"
    embedding = await embedding_service.embed(embed_text)
    opp = Opportunity(**body.model_dump(), embedding=embedding)
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    return opp
