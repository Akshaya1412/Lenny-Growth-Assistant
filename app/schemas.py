from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    user_name: str = Field(default="internal-user", min_length=1, max_length=128)


class SessionRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    provider: Optional[str] = None
    artifact_type: Optional[Literal["markdown", "html"]] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    citations: List[str]
    provider: str
    fallback_used: bool
    artifact: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    database_status: str
    provider: str
    fallback_provider: str
    model: Optional[str] = None
    service: str = "lenny-growth-assistant"


class ArtifactRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    artifact_type: Literal["markdown", "html"] = "markdown"
    source_text: Optional[str] = None
