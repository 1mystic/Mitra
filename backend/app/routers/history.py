"""Chat history — conversation CRUD and message persistence."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.db import ChatHistoryMessage, Conversation
from ..models.schemas import (
    ChatHistoryMessageCreate,
    ChatHistoryMessageRead,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
)

router = APIRouter(prefix="/api/history", tags=["history"])


# ── Conversations ─────────────────────────────────────────────────────────────

@router.get("/conversations/{user_id}", response_model=list[ConversationRead])
async def list_conversations(user_id: str, db: AsyncSession = Depends(get_db)):
    """Return all conversations for a user, most-recent first, with message counts."""
    result = await db.execute(
        select(
            Conversation,
            func.count(ChatHistoryMessage.id).label("message_count"),
        )
        .outerjoin(ChatHistoryMessage, ChatHistoryMessage.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = result.all()
    out = []
    for conv, count in rows:
        d = ConversationRead.model_validate(conv)
        d.message_count = count or 0
        out.append(d)
    return out


@router.post("/conversations", response_model=ConversationRead, status_code=201)
async def create_conversation(body: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conv = Conversation(
        user_id=body.user_id,
        title=body.title or "New chat",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    d = ConversationRead.model_validate(conv)
    d.message_count = 0
    return d


@router.get("/conversations/{conv_id}/messages", response_model=ConversationWithMessages)
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conv_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    out = ConversationWithMessages.model_validate(conv)
    out.message_count = len(conv.messages)
    return out


@router.patch("/conversations/{conv_id}", response_model=ConversationRead)
async def update_conversation(conv_id: str, body: ConversationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = body.title
    conv.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(conv)
    d = ConversationRead.model_validate(conv)
    d.message_count = 0
    return d


@router.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()


# ── Messages ──────────────────────────────────────────────────────────────────

@router.post("/messages", response_model=ChatHistoryMessageRead, status_code=201)
async def add_message(body: ChatHistoryMessageCreate, db: AsyncSession = Depends(get_db)):
    # Touch conversation updated_at so it bubbles to top of list
    await db.execute(
        select(Conversation).where(Conversation.id == body.conversation_id)
    )
    msg = ChatHistoryMessage(
        conversation_id=body.conversation_id,
        role=body.role,
        content=body.content,
    )
    db.add(msg)
    # Bump updated_at on the parent conversation
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == body.conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg
