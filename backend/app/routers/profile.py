import io

import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.db import SkillProfile, User
from ..models.schemas import ProfileUploadResponse, SkillProfileRead
from ..services import embedding_service, resume_service, skill_graph

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _extract_text_from_pdf(data: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


@router.post("/upload", response_model=ProfileUploadResponse)
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
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    filename = file.filename or ""
    try:
        if file.content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            resume_text = _extract_text_from_pdf(raw)
        else:
            resume_text = raw.decode("utf-8", errors="ignore")
    except Exception as exc:  # pdfplumber can raise on corrupt PDFs
        raise HTTPException(status_code=422, detail=f"Could not read file: {exc}") from exc

    if not resume_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract any text from this file. If it's a scanned PDF, please upload a text-based PDF.",
        )

    # Extract structured skill profile
    extracted = await skill_graph.extract_from_text(resume_text)

    # Build profile-level embedding (skills + project descriptions)
    embed_text = (
        " ".join(extracted["skills"].keys())
        + " "
        + " ".join(p.get("description", "") for p in extracted["projects"])
    ).strip() or resume_text[:1000]
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

    # Chunk + embed + persist for RAG retrieval (separate transaction)
    chunk_count = await resume_service.store_chunks(db, user_id, resume_text)

    return ProfileUploadResponse(
        **SkillProfileRead.model_validate(profile).model_dump(),
        chunk_count=chunk_count,
    )


@router.get("/{user_id}", response_model=SkillProfileRead)
async def get_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SkillProfile).where(SkillProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")
    return profile
