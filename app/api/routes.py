from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ChatMessage, ChatSession
from app.schemas import ArtifactRequest, ChatRequest, SessionCreate, SessionRename
from app.services.agent import answer_question, create_artifact_from_conversation, create_ship30_essay
from app.services.llm import provider_status

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database_status = "up"
    except Exception:
        database_status = "degraded"

    provider_state = provider_status()
    return {
        "status": "ok",
        "database_status": database_status,
        "provider": settings.model_provider,
        "fallback_provider": "mock",
        "model": (
            settings.ollama_model
            if settings.model_provider == "ollama"
            else settings.openai_model
            if settings.model_provider == "openai"
            else settings.anthropic_model
        ),
        "service": "lenny-growth-assistant",
        "ollama_available": provider_state["ollama_available"],
    }


@router.get("/config")
def config() -> dict:
    provider_state = provider_status()
    return {
        "provider": settings.model_provider,
        "available_providers": ["ollama", "openai", "anthropic", "claude_agent_sdk", "mock"],
        "provider_availability": {
            "ollama": provider_state["ollama_available"],
            "openai": provider_state["openai_configured"],
            "anthropic": provider_state["anthropic_configured"],
            "claude_agent_sdk": provider_state["claude_agent_sdk_configured"] and provider_state["claude_agent_sdk_available"],
        },
        "fallback_provider": "mock",
        "model": (
            settings.ollama_model
            if settings.model_provider == "ollama"
            else settings.openai_model
            if settings.model_provider == "openai"
            else settings.anthropic_model
        ),
        "ollama_available": provider_state["ollama_available"],
        "ollama_detail": provider_state["ollama_detail"],
    }


@router.post("/sessions")
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    session = ChatSession(user_name=payload.user_name, title="New Lenny conversation")
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "user_name": session.user_name, "title": session.title, "created_at": session.created_at.isoformat()}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    first_user_message = (
        db.query(ChatMessage.content)
        .filter(ChatMessage.session_id == ChatSession.id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .limit(1)
        .scalar_subquery()
    )
    sessions = db.query(ChatSession, first_user_message.label("preview")).order_by(ChatSession.updated_at.desc()).all()
    return [
        {
            "id": session.id,
            "user_name": session.user_name,
            "title": session.title,
            "preview": preview,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
        for session, preview in sessions
    ]


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, payload: SessionRename, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title cannot be empty")
    session.title = title
    db.commit()
    db.refresh(session)
    return {"id": session.id, "title": session.title, "updated_at": session.updated_at.isoformat()}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"id": session_id, "deleted": True}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "citations": json.loads(msg.citations) if msg.citations else [],
            "created_at": msg.created_at.isoformat(),
            "artifact": msg.artifact,
        }
        for msg in session.messages
    ]
    return {"id": session.id, "user_name": session.user_name, "title": session.title, "messages": messages}


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=payload.message,
        created_at=datetime.now(timezone.utc),
    )
    if session.title == "New Lenny conversation":
        title = payload.message.strip()
        session.title = title[:72].rstrip() + ("..." if len(title) > 72 else "")
    db.add(user_message)
    db.commit()

    recent_messages = [
        {"role": message.role, "content": message.content}
        for message in session.messages
    ]
    response = answer_question(payload.message, recent_messages=recent_messages, provider=payload.provider or settings.model_provider)
    if response.get("provider_error"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response["answer"])

    artifact_payload = None
    if payload.artifact_type:
        artifact_payload = create_artifact_from_conversation(
            topic=payload.message,
            source_text=response["answer"],
            artifact_type=payload.artifact_type,
        )

    bot_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response["answer"],
        citations=json.dumps(response["citations"]),
        artifact=artifact_payload,
    )
    db.add(bot_message)
    db.commit()
    db.refresh(bot_message)

    session.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "session_id": session_id,
        "reply": response["answer"],
        "citations": response["citations"],
        "provider": response["provider"],
        "fallback_used": response["fallback_used"],
        "artifact": artifact_payload,
    }


@router.post("/sessions/{session_id}/ship30")
def ship30(session_id: str, payload: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    selected_provider = payload.provider or settings.model_provider
    essay = create_ship30_essay(payload.message or "Ship 30 for 30 writing discipline", provider=selected_provider)
    if essay["fallback_used"] and selected_provider != "mock":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=essay["content"])
    artifact = {
        "type": "html",
        "content": f"<h1>{essay['title']}</h1><div>{essay['content']}</div>",
    }
    bot_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=essay["content"],
        citations=json.dumps(essay["citations"]),
        artifact=artifact,
    )
    db.add(bot_message)
    db.commit()
    return {"session_id": session_id, "essay": essay["content"], "citations": essay["citations"], "artifact": artifact}


@router.post("/artifacts")
def create_artifact(req: ArtifactRequest):
    artifact = create_artifact_from_conversation(topic=req.topic, source_text=req.source_text or req.topic, artifact_type=req.artifact_type)
    return {"type": artifact["type"], "content": artifact["content"], "title": req.topic}
