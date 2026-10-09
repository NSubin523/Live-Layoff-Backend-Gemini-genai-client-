from dataclasses import dataclass
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, List, Optional

from app.features.chat_ai.tools.classifier.greeting_classifier import is_greeting
from app.features.chat_ai.tools.extractor.intent_extractor import (
    CONTEXT_MESSAGE_LIMIT, extract_intent,
)
from app.features.chat_ai.tools.loader.prompt_loader import prompt_loader
from app.features.chat_ai.data.dto.chat_dto import (
    ChatIntent,
    CreateChatMessage,
    CompanyCard,
    LayoffRecord,
)
from app.features.chat_ai.data.model.chat_message import ChatIntentType, ChatRole
from app.features.chat_ai.data.repository.chat_repository import (
    ChatRepository,
)
from app.features.chat_ai.data.repository.layoff_lookup_repository import (
    LayoffLookupRepository,
)
from app.services.gemini.base_gemini_service import BaseGeminiService

TIME_WINDOW_DAYS = {"week": 7, "month": 30, "year": 365}
MAX_CARDS = 5
logger = logging.getLogger(__name__)


@dataclass
class ChatStreamEvent:
    """Domain event yielded by the service. The route formats these as SSE."""

    type: str  # "intent" | "cards" | "text" | "done" | "error"
    data: Any = None


class ChatService:
    """Conductor: save -> classify -> branch -> retrieve -> generate -> save.

    Owns no regex, no prompt text, no Firestore calls directly —
    those live in the classifier, prompts/, and repository layers.
    """

    def __init__(
        self,
        history: Optional[ChatRepository] = None,
        lookup: Optional[LayoffLookupRepository] = None,
        gemini: Optional[BaseGeminiService] = None,
    ):
        self.history = history or ChatRepository()
        self.lookup = lookup or LayoffLookupRepository()
        self.gemini = gemini or BaseGeminiService()

    def chat(self, user_id: str, message: str) -> Iterator[ChatStreamEvent]:
        """Streams the agent turn. message is already validated + normalized
        by ChatRequest before it gets here."""
        try:
            greeting = is_greeting(message)
            # Read before saving so the current message appears exactly once
            # in the classifier input. The repository returns oldest-first.
            context = [] if greeting else self.history.get_history(
                user_id, limit=CONTEXT_MESSAGE_LIMIT
            ).messages
            self.history.save(
                CreateChatMessage(user_id=user_id, role=ChatRole.USER, text=message)
            )
            if greeting:
                yield ChatStreamEvent(
                    "intent", {"intent": ChatIntentType.GREETING.value}
                )
                yield from self._canned(
                    user_id, ChatIntentType.GREETING, "greeting"
                )
            else:
                intent = extract_intent(message, history=context)
                yield ChatStreamEvent("intent", {"intent": intent.intent.value})

                if intent.intent == ChatIntentType.GREETING:
                    yield from self._canned(user_id, intent.intent, "greeting")
                elif intent.intent == ChatIntentType.CAPABILITIES:
                    yield from self._canned(user_id, intent.intent, "capabilities")
                elif intent.intent in (
                    ChatIntentType.CLARIFICATION, ChatIntentType.CONVERSATION
                ):
                    text = (intent.response_text or "").strip()
                    if not text:
                        text = prompt_loader.get_loader("clarification")
                    yield from self._reply(user_id, intent.intent, text)
                elif intent.intent == ChatIntentType.OUT_OF_SCOPE:
                    yield from self._canned(
                        user_id, ChatIntentType.OUT_OF_SCOPE, "out_of_scope"
                    )
                else:
                    yield from self._layoff_query(
                        user_id, intent.resolved_query or message, intent
                    )
        except Exception:
            logger.exception("Chat response failed while streaming")
            # The failed agent turn is not persisted.
            yield ChatStreamEvent(
                "error",
                {"message": "Something went wrong on our end. Please try again."},
            )
        yield ChatStreamEvent("done")

    # -- branches ----------------------------------------------------

    def _canned(
        self, user_id: str, intent_type: ChatIntentType, prompt_key: str
    ) -> Iterator[ChatStreamEvent]:
        """Zero-model branch: canned text, no cards."""
        text = prompt_loader.get_loader(prompt_key)
        yield from self._reply(user_id, intent_type, text)

    def _reply(
        self, user_id: str, intent_type: ChatIntentType, text: str
    ) -> Iterator[ChatStreamEvent]:
        yield ChatStreamEvent("text", {"chunk": text})
        self.history.save(
            CreateChatMessage(
                user_id=user_id,
                role=ChatRole.AGENT,
                text=text,
                intent=intent_type,
                card_ids=[],
            )
        )

    def _layoff_query(
        self, user_id: str, message: str, intent: ChatIntent
    ) -> Iterator[ChatStreamEvent]:
        since = self._since_from_window(intent.time_window)
        records = self._retrieve(intent, since)
        cards = self._build_cards(records)

        if cards:
            yield ChatStreamEvent(
                "cards", [c.model_dump(mode="json") for c in cards]
            )

        prompt = prompt_loader.get_loader("answer_template").format(
            message=message,
            records=self._records_json(records),
        )
        chunks: List[str] = []
        for chunk in self.gemini.stream_text(
            prompt=prompt,
            system_instruction=prompt_loader.get_loader("answer_system"),
        ):
            chunks.append(chunk)
            yield ChatStreamEvent("text", {"chunk": chunk})

        self.history.save(
            CreateChatMessage(
                user_id=user_id,
                role=ChatRole.AGENT,
                text="".join(chunks),
                intent=intent.intent,
                card_ids=[c.layoff_id for c in cards],
            )
        )

    # -- helpers -----------------------------------------------------

    def _since_from_window(self, time_window: Optional[str]) -> Optional[datetime]:
        if not time_window or time_window not in TIME_WINDOW_DAYS:
            return None
        return datetime.now(timezone.utc) - timedelta(
            days=TIME_WINDOW_DAYS[time_window]
        )

    def _retrieve(
        self, intent: ChatIntent, since: Optional[datetime]
    ) -> List[LayoffRecord]:
        if intent.companies:
            return self.lookup.find_by_companies(intent.companies, since=since)
        if intent.industry:
            return self.lookup.find_by_industry(intent.industry, since=since)
        return self.lookup.find_latest(since=since)

    def _build_cards(self, records: List[LayoffRecord]) -> List[CompanyCard]:
        """One card per company (its newest record), capped."""
        seen = set()
        cards: List[CompanyCard] = []
        for r in records:
            if r.company_name in seen:
                continue
            seen.add(r.company_name)
            cards.append(
                CompanyCard(
                    layoff_id=r.id,
                    company_name=r.company_name,
                    logo_url=r.logo_url,
                    impact_count=r.impact_count,
                    status=r.status,
                    headline=r.summary,
                    reported_at=r.reported_at,
                )
            )
            if len(cards) >= MAX_CARDS:
                break
        return cards

    def _records_json(self, records: List[LayoffRecord]) -> str:
        import json

        slim = [
            {
                "company_name": r.company_name,
                "impact_count": r.impact_count,
                "status": r.status,
                "industry": r.industry,
                "location": r.location,
                "summary": r.summary,
                "reported_at": r.reported_at.isoformat() if r.reported_at else None,
            }
            for r in records
        ]
        return json.dumps(slim, default=str)
