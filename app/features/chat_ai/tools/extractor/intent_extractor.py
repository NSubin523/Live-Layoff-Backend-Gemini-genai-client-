import json
from datetime import datetime, timezone
from typing import Optional, Sequence

from app.features.chat_ai.data.dto.chat_dto import ChatIntent
from app.features.chat_ai.data.model.chat_message import ChatMessage
from app.features.chat_ai.tools.loader.prompt_loader import prompt_loader
from app.services.gemini.base_gemini_service import BaseGeminiService

_service: Optional[BaseGeminiService] = None
CONTEXT_MESSAGE_LIMIT = 12
CONTEXT_TEXT_LIMIT = 1200


def _gemini() -> BaseGeminiService:
    """Lazy singleton: creating the client at import time would require
    the API key just to import this module."""
    global _service
    if _service is None:
        _service = BaseGeminiService()
    return _service


def extract_intent(
    message: str, history: Sequence[ChatMessage] = ()
) -> ChatIntent:
    """Resolve the current request using bounded, unexpired prior messages.

    Assumes the message is already normalized (ChatRequest does this).
    """
    now = datetime.now(timezone.utc)
    context = [
        {"role": item.role.value, "text": item.text[:CONTEXT_TEXT_LIMIT],
         "intent": item.intent.value if item.intent else None}
        for item in history[-CONTEXT_MESSAGE_LIMIT:]
        if item.expires_at > now
    ]
    return _gemini().generate_structured_output(
        prompt=json.dumps({"recent_conversation": context, "current_message": message}),
        response_schema=ChatIntent,
        system_instruction=prompt_loader.get_loader("intent_system"),
    )
