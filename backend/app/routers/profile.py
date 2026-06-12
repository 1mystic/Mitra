import io

import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.db import SkillProfile, User
from ..models.schemas import SkillProfileRead
from ..services import embedding_service, skill_graph

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _extract_text_from_pdf(data: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


@router.post("/upload", response_model=SkillProfileRead)
async def upload_resume(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    raw = await file.read()

    if file.content_type == "application/pdf" or file.filename.endswith(".pdf"):
        resume_text = _extract_text_from_pdf(raw)
    else:
        resume_text = raw.decode("utf-8", errors="ignore")

    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file")

    # Extract skills
    extracted = await skill_graph.extract_from_text(resume_text)

    # Build profile embedding
    embed_text = (
        " ".join(extracted["skills"].keys())
        + " "
        + " ".join(p.get("description", "") for p in extracted["projects"])
    )
    embedding = await embedding_service.embed(embed_text)

    # Upsert SkillProfile
    res = await db.execute(select(SkillProfile).where(SkillProfile.user_id == user_id))
    profile = res.scalar_one_or_none()
    if profile:
        profile.resume_text = resume_text
        profile.skills = extracted["skills"]
        profile.projects = extracted["projects"]
        profile.experience_text = extracted["experience_summary"]
        profile.embedding = embedding
    else:
        profile = SkillProfile(
            user_id=user_id,
            resume_text=resume_text,
            skills=extracted["skills"],
            projects=extracted["projects"],
            experience_text=extracted["experience_summary"],
            embedding=embedding,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{user_id}", response_model=SkillProfileRead)
async def get_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SkillProfile).where(SkillProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")
    return profile
