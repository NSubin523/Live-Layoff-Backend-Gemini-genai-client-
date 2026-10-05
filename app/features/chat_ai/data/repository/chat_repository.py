from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from app.features.chat_ai.data.dto.chat_dto import ChatHistoryResponse, CreateChatMessage
from app.features.chat_ai.data.model.chat_message import (
    ChatIntentType,
    ChatMessage,
    ChatRole,
)
from app.services.firebase import firebase_config

HISTORY_TTL = timedelta(hours=24)
DEFAULT_PAGE_SIZE = 20


class ChatRepository:
    """Persists chat messages under chat_history/{user_id}/messages/.

    created_at/expires_at use this server's clock, not the client's.
    (SERVER_TIMESTAMP can't be used here because expires_at is computed
    as created_at + 24h, which needs a concrete value.)
    """

    def _collection(self, user_id: str):
        db = firebase_config.db
        if db is None:
            raise RuntimeError("Database connection uninitialized")
        return db.collection("chat_history").document(user_id).collection("messages")

    def _to_message(self, doc) -> ChatMessage:
        data = doc.to_dict()
        return ChatMessage(
            message_id=doc.id,
            user_id=data["user_id"],
            role=ChatRole(data["role"]),
            text=data["text"],
            intent=ChatIntentType(data["intent"]) if data.get("intent") else None,
            card_ids=data.get("card_ids") or [],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
        )

    def save(self, message: CreateChatMessage) -> ChatMessage:
        """Persists one message (user or agent) and returns the complete
        stored document with its assigned id and timestamps."""
        now = datetime.now(timezone.utc)
        doc_ref = self._collection(message.user_id).document()
        doc_ref.set(
            {
                "user_id": message.user_id,
                "role": message.role.value,
                "text": message.text,
                "intent": message.intent.value if message.intent else None,
                "card_ids": message.card_ids,
                "created_at": now,
                "expires_at": now + HISTORY_TTL,
            }
        )
        return ChatMessage(
            message_id=doc_ref.id,
            user_id=message.user_id,
            role=message.role,
            text=message.text,
            intent=message.intent,
            card_ids=message.card_ids,
            created_at=now,
            expires_at=now + HISTORY_TTL,
        )

    def get_history(
        self,
        user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        before: Optional[datetime] = None,
    ) -> ChatHistoryResponse:
        # where + order_by on the SAME field needs no composite index.
        query = self._collection(user_id).order_by("created_at", direction="DESCENDING")
        if before is not None:
            query = query.where(filter=FieldFilter("created_at", "<", before))

        docs = list(query.limit(limit + 1).stream())
        has_more = len(docs) > limit
        docs = docs[:limit]

        # Oldest-first for direct UI rendering.
        messages = [self._to_message(d) for d in reversed(docs)]
        next_before = messages[0].created_at if has_more and messages else None
        return ChatHistoryResponse(
            messages=messages, has_more=has_more, next_before=next_before
        )
