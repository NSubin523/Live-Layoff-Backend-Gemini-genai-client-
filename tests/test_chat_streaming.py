import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.features.auth.service.auth_deps import get_current_user_id
from app.features.chat_ai.api import chat_routes
from app.features.chat_ai.data.dto.chat_dto import ChatIntent, LayoffRecord
from app.features.chat_ai.data.model.chat_message import ChatIntentType, ChatRole
from app.features.chat_ai.service.chat_service import ChatService
from app.services.gemini.base_gemini_service import BaseGeminiService


class ChatStreamingTests(unittest.TestCase):
    def setUp(self):
        self.history = Mock()
        self.history.get_history.return_value.messages = []
        self.lookup = Mock()
        self.gemini = Mock()
        self.service = ChatService(self.history, self.lookup, self.gemini)
        app = FastAPI()
        app.include_router(chat_routes.router)
        app.dependency_overrides[get_current_user_id] = lambda: "test-user"
        self.client = TestClient(app)

    def events(self, message):
        with patch.object(chat_routes, "_chat_service", return_value=self.service):
            response = self.client.post("/api/v1/chat", json={"message": message})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        return [
            (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
            for block in response.text.strip().split("\n\n")
            if (lines := block.splitlines())
        ]

    def test_greeting_emits_text_and_persists_both_messages(self):
        events = self.events("hi")
        self.assertEqual([event[0] for event in events], ["intent", "text", "done"])
        self.assertEqual(events[0][1], {"intent": "greeting"})
        self.assertTrue(events[1][1]["chunk"])
        saved = [call.args[0] for call in self.history.save.call_args_list]
        self.assertEqual([message.role for message in saved], [ChatRole.USER, ChatRole.AGENT])
        self.assertEqual(saved[1].text, events[1][1]["chunk"])
        self.gemini.stream_text.assert_not_called()

    def test_out_of_scope_emits_canned_text(self):
        with patch("app.features.chat_ai.service.chat_service.extract_intent",
                   return_value=ChatIntent(intent=ChatIntentType.OUT_OF_SCOPE)):
            events = self.events("Write a recipe")
        self.assertEqual([event[0] for event in events], ["intent", "text", "done"])
        self.assertTrue(events[1][1]["chunk"])
        self.gemini.stream_text.assert_not_called()

    def test_layoff_answer_streams_cards_and_chunks_and_saves_full_text(self):
        self.lookup.find_latest.return_value = [LayoffRecord(id="record-1", company_name="Example")]
        self.gemini.stream_text.return_value = iter(["Latest ", "layoffs."])
        with patch("app.features.chat_ai.service.chat_service.extract_intent",
                   return_value=ChatIntent(intent=ChatIntentType.LAYOFF_QUERY)):
            events = self.events("What are the latest layoffs?")
        self.assertEqual([event[0] for event in events], ["intent", "cards", "text", "text", "done"])
        self.assertEqual(events[1][1][0]["layoff_id"], "record-1")
        saved = self.history.save.call_args.args[0]
        self.assertEqual(saved.text, "Latest layoffs.")
        self.assertEqual(saved.card_ids, ["record-1"])

    def test_model_failure_emits_error_then_done_without_saving_partial_answer(self):
        self.lookup.find_latest.return_value = []
        def failing_stream(**kwargs):
            yield "Partial"
            raise RuntimeError("upstream unavailable")
        self.gemini.stream_text.side_effect = failing_stream
        with patch("app.features.chat_ai.service.chat_service.extract_intent",
                   return_value=ChatIntent(intent=ChatIntentType.LAYOFF_QUERY)):
            with self.assertLogs("app.features.chat_ai.service.chat_service", level="ERROR"):
                events = self.events("latest layoffs")
        self.assertEqual([event[0] for event in events], ["intent", "text", "error", "done"])
        self.assertNotIn("upstream unavailable", json.dumps(events))
        self.assertEqual(self.history.save.call_count, 1)


class GeminiStreamingTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        with patch("app.services.gemini.base_gemini_service.genai.Client", return_value=self.client):
            self.service = BaseGeminiService()

    def test_sdk_text_chunks_skip_empty_metadata(self):
        self.client.models.generate_content_stream.return_value = iter([
            SimpleNamespace(text=None), SimpleNamespace(text="Hello "),
            SimpleNamespace(text=""), SimpleNamespace(text="world"),
        ])
        self.assertEqual(list(self.service.stream_text("question", "system")), ["Hello ", "world"])
        kwargs = self.client.models.generate_content_stream.call_args.kwargs
        self.assertEqual(kwargs["contents"], "question")
        self.assertEqual(kwargs["config"].system_instruction, "system")

    def test_empty_sdk_response_is_an_error(self):
        self.client.models.generate_content_stream.return_value = iter([SimpleNamespace(text=None)])
        with self.assertRaisesRegex(ValueError, "empty generation response"):
            list(self.service.stream_text("question"))

    def test_sdk_failure_propagates_to_chat_error_handler(self):
        self.client.models.generate_content_stream.side_effect = RuntimeError("network failure")
        with self.assertRaisesRegex(RuntimeError, "network failure"):
            list(self.service.stream_text("question"))


if __name__ == "__main__":
    unittest.main()
