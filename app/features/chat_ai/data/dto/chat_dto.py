from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from app.features.chat_ai.data.model.chat_message import ChatMessage, ChatRole
from app.features.chat_ai.data.model.chat_message import ChatIntentType


class ChatRequest(BaseModel):
    """POST /api/v1/chat body.

    Carries only the raw text. user_id is taken from the auth token
    server-side and must never come from the client.
    """

    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("message must not be blank")
        return v

class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage]
    has_more: bool
    next_before: Optional[datetime] = None

class ChatIntent(BaseModel):
    intent: ChatIntentType
    resolved_query: Optional[str] = Field(
        default=None, max_length=1000,
        description="Standalone layoff question resolved from the latest message and relevant conversation context. No factual answers.",
    )
    response_text: Optional[str] = Field(
        default=None, max_length=500,
        description="Short clarification question or conversational acknowledgment. Never include layoff facts here.",
    )
    companies: List[str] = Field(
        default_factory=list,
        description="Company names mentioned, e.g. ['Microsoft']",
    )
    industry: Optional[str] = Field(
        default=None,
        description="Industry filter if the user named one, e.g. 'Software'",
    )
    time_window: Optional[str] = Field(
        default=None,
        description="Recency hint: 'week', 'month' or 'year', if implied",
    )

class CreateChatMessage(BaseModel):
    user_id: str
    role: ChatRole
    text: str
    intent: Optional[ChatIntentType] = None
    card_ids: List[str] = Field(default_factory=list)

class LayoffRecord(BaseModel):
    """A layoff event from the shared 'layoffs' collection (owned by feed).
    Read-only for chat — chat never writes here."""

    id: str
    company_name: str
    impact_count: Optional[int] = None
    status: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    company_site: Optional[str] = None
    summary: Optional[str] = None
    trend_direction: Optional[str] = None
    logo_url: Optional[str] = None
    reported_at: Optional[datetime] = None


class CompanyCard(BaseModel):
    """Card payload streamed to FE. Tapping it opens the existing
    feed-detail bottom sheet for the layoff record."""

    layoff_id: str
    company_name: str
    logo_url: Optional[str] = None
    impact_count: Optional[int] = None
    status: Optional[str] = None
    headline: Optional[str] = None
    reported_at: Optional[datetime] = None
