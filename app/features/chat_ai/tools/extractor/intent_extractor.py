from typing import Optional

from app.features.chat_ai.data.dto.chat_dto import ChatIntent
from app.features.chat_ai.tools.loader.prompt_loader import prompt_loader
from app.services.gemini.base_gemini_service import BaseGeminiService

_service: Optional[BaseGeminiService] = None


def _gemini() -> BaseGeminiService:
    """Lazy singleton: creating the client at import time would require
    the API key just to import this module."""
    global _service
    if _service is None:
        _service = BaseGeminiService()
    return _service


def extract_intent(message: str) -> ChatIntent:
    """Model-backed intent decode. Returns layoff_query or out_of_scope
    plus extracted companies / industry / time window.

    Assumes the message is already normalized (ChatRequest does this).
    """
    return _gemini().generate_structured_output(
        prompt=message,
        response_schema=ChatIntent,
        system_instruction=prompt_loader.get_loader("intent_system"),
    )
