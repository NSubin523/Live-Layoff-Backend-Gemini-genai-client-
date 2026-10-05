import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.features.auth.service.auth_deps import get_current_user_id
from app.features.chat_ai.data.dto.chat_dto import ChatHistoryResponse, ChatRequest
from app.features.chat_ai.data.repository.chat_repository import (
    ChatRepository,
)
from app.features.chat_ai.service.chat_service import ChatService, ChatStreamEvent

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

_service: Optional[ChatService] = None
_history_repo: Optional[ChatRepository] = None


def _chat_service() -> ChatService:
    """Lazy singleton: building it at import time would require the
    Gemini API key just to import this module."""
    global _service
    if _service is None:
        _service = ChatService()
    return _service


def _history() -> ChatRepository:
    global _history_repo
    if _history_repo is None:
        _history_repo = ChatRepository()
    return _history_repo


def _require_user(user_id: str) -> str:
    # Chat is login-only: no guest access.
    if not user_id or user_id == "Non-User":
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def _to_sse(event: ChatStreamEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, default=str)}\n\n"


@router.post("")
def post_chat(body: ChatRequest, user_id: str = Depends(get_current_user_id)):
    """Streams the agent turn as SSE: intent -> cards? -> text* -> done."""
    _require_user(user_id)
    # body.message is validated (1-500 chars) and normalized by ChatRequest.
    stream = (_to_sse(e) for e in _chat_service().chat(user_id, body.message))
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/history", response_model=ChatHistoryResponse)
def get_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=20, ge=1, le=50),
    before: Optional[str] = None,
):
    """Cursor-paginated history, oldest-first. `before` is the ISO
    timestamp from the previous page's `next_before`."""
    _require_user(user_id)
    cursor: Optional[datetime] = None
    if before:
        try:
            cursor = datetime.fromisoformat(before)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid 'before' timestamp"
            )
        if cursor.tzinfo is None:
            cursor = cursor.replace(tzinfo=timezone.utc)
    return _history().get_history(user_id, limit=limit, before=cursor)
