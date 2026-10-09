from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    Firestore document: chat_history/{user_id}/messages/{message_id}

    message_id is the firestore auto-generated document id for each message
    created_at uses the server timestamp; expires at = created_at + 24h
    """

    message_id: str
    user_id: str
    role: ChatRole
    text: str
    intent: Optional[ChatIntentType] = None
    card_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime

class ChatRole(str, Enum):
    USER = "user"
    AGENT = "agent"

class ChatIntentType(str, Enum):
    GREETING = "greeting"
    CAPABILITIES = "capabilities"
    CLARIFICATION = "clarification"
    CONVERSATION = "conversation"
    LAYOFF_QUERY = "layoff_query"
    OUT_OF_SCOPE = "out_of_scope"
