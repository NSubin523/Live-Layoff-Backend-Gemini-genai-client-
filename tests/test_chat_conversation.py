import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app.features.chat_ai.data.dto.chat_dto import ChatIntent
from app.features.chat_ai.data.model.chat_message import ChatIntentType, ChatMessage, ChatRole
from app.features.chat_ai.service.chat_service import ChatService
from app.features.chat_ai.tools.extractor.intent_extractor import extract_intent


def prior(text, role=ChatRole.USER, **kwargs):
    now = datetime.now(timezone.utc)
    return ChatMessage(message_id="old", user_id="user-1", role=role, text=text,
                       created_at=now, expires_at=kwargs.pop("expires_at", now + timedelta(hours=1)), **kwargs)


class IntentContextTests(unittest.TestCase):
    def test_context_is_ordered_bounded_and_excludes_expired_messages(self):
        history = [prior(str(i)) for i in range(15)]
        history[-2] = prior("expired", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        history[-1] = prior("x" * 5000, ChatRole.AGENT, intent=ChatIntentType.CLARIFICATION)
        gemini = Mock()
        with patch("app.features.chat_ai.tools.extractor.intent_extractor._gemini", return_value=gemini):
            extract_intent("sure", history)
        payload = json.loads(gemini.generate_structured_output.call_args.kwargs["prompt"])
        self.assertEqual(payload["current_message"], "sure")
        context = payload["recent_conversation"]
        self.assertEqual(len(context), 11)
        self.assertEqual(context[0]["text"], "3")
        self.assertNotIn("expired", [item["text"] for item in context])
        self.assertEqual(len(context[-1]["text"]), 1200)
        self.assertEqual(context[-1]["role"], "agent")
        self.assertEqual(context[-1]["intent"], "clarification")


class ConversationServiceTests(unittest.TestCase):
    def setUp(self):
        self.history, self.lookup, self.gemini = Mock(), Mock(), Mock()
        self.history.get_history.return_value.messages = [prior("Is Meta laying off?")]
        self.lookup.find_by_companies.return_value = []
        self.lookup.find_latest.return_value = []
        self.gemini.stream_text.side_effect = lambda **kwargs: iter(["Answer from records."])
        self.service = ChatService(self.history, self.lookup, self.gemini)

    def turn(self, message, intent):
        with patch("app.features.chat_ai.service.chat_service.extract_intent", return_value=intent) as classifier:
            events = list(self.service.chat("user-1", message))
        self.assertEqual(events[-1].type, "done")
        self.assertNotIn("error", [e.type for e in events])
        return events, classifier

    def test_follow_up_passes_prior_history_and_resolved_question_to_answer(self):
        intent = ChatIntent(intent=ChatIntentType.LAYOFF_QUERY, companies=["Meta"],
                            time_window="month", resolved_query="What layoffs were reported at Meta in the last 30 days?")
        _, classifier = self.turn("what about last month?", intent)
        self.history.get_history.assert_called_once_with("user-1", limit=12)
        classifier.assert_called_once_with("what about last month?", history=self.history.get_history.return_value.messages)
        kwargs = self.lookup.find_by_companies.call_args
        self.assertEqual(kwargs.args[0], ["Meta"])
        self.assertIsNotNone(kwargs.kwargs["since"])
        self.assertIn(intent.resolved_query, self.gemini.stream_text.call_args.kwargs["prompt"])
        self.assertEqual(self.history.save.call_args_list[0].args[0].text, "what about last month?")

    def test_capabilities_is_helpful_and_does_not_retrieve(self):
        events, _ = self.turn("what can you help me with", ChatIntent(intent=ChatIntentType.CAPABILITIES))
        self.assertIn("latest layoffs overall", events[1].data["chunk"])
        self.assertEqual(self.history.save.call_args.args[0].intent, ChatIntentType.CAPABILITIES)
        self.lookup.find_latest.assert_not_called()
        self.gemini.stream_text.assert_not_called()

    def test_sure_asks_contextual_clarification(self):
        question = "Do you want the latest layoffs overall or a specific company?"
        events, _ = self.turn("sure", ChatIntent(intent=ChatIntentType.CLARIFICATION, response_text=question))
        self.assertEqual(events[1].data["chunk"], question)
        self.assertEqual(self.history.save.call_args.args[0].text, question)
        self.gemini.stream_text.assert_not_called()

    def test_missing_clarification_text_has_useful_fallback(self):
        events, _ = self.turn("sure", ChatIntent(intent=ChatIntentType.CLARIFICATION))
        self.assertIn("latest layoffs overall", events[1].data["chunk"])

    def test_latest_overall_uses_no_previous_company_filter(self):
        self.turn("sure give me latest data", ChatIntent(intent=ChatIntentType.LAYOFF_QUERY,
                  resolved_query="What are the latest reported layoffs overall?"))
        self.lookup.find_latest.assert_called_once_with(since=None)
        self.lookup.find_by_companies.assert_not_called()

    def test_explicit_unrelated_topic_does_not_retrieve_old_company(self):
        events, _ = self.turn("when was Einstein born", ChatIntent(intent=ChatIntentType.OUT_OF_SCOPE))
        self.assertEqual(events[0].data["intent"], "out_of_scope")
        self.lookup.find_by_companies.assert_not_called()
        self.gemini.stream_text.assert_not_called()

    def test_thanks_gets_conversational_reply(self):
        events, _ = self.turn("thanks", ChatIntent(intent=ChatIntentType.CONVERSATION, response_text="You're welcome!"))
        self.assertEqual(events[1].data["chunk"], "You're welcome!")
        self.gemini.stream_text.assert_not_called()

    def test_history_read_happens_before_current_message_save(self):
        self.history.get_history.side_effect = lambda *args, **kwargs: (
            self.assertEqual(self.history.save.call_count, 0) or Mock(messages=[]))
        self.turn("sure", ChatIntent(intent=ChatIntentType.CLARIFICATION))

    def test_history_failure_is_reported_as_sse_error(self):
        self.history.get_history.side_effect = RuntimeError("database unavailable")
        with self.assertLogs("app.features.chat_ai.service.chat_service", level="ERROR"):
            events = list(self.service.chat("user-1", "sure"))
        self.assertEqual([e.type for e in events], ["error", "done"])
        self.history.save.assert_not_called()

    def test_pure_greeting_keeps_fast_path(self):
        list(self.service.chat("user-1", "hi"))
        self.history.get_history.assert_not_called()
