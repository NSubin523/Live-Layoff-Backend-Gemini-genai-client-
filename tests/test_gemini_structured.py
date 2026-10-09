import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import BaseModel
from app.services.gemini.base_gemini_service import BaseGeminiService


class Metrics(BaseModel):
    company: str
    impact_count: int


class GeminiStructuredTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        with patch('app.services.gemini.base_gemini_service.genai.Client', return_value=self.client):
            self.service = BaseGeminiService(model_name='test-model')

    def test_json_response_is_validated_into_requested_schema(self):
        self.client.models.generate_content.return_value = SimpleNamespace(text='{"company":"Meta","impact_count":42}')
        result = self.service.generate_structured_output('story', Metrics, 'extract metrics')
        self.assertIsInstance(result, Metrics)
        self.assertEqual(result.impact_count, 42)
        kwargs = self.client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs['model'], 'test-model')
        self.assertEqual(kwargs['contents'], 'story')
        self.assertIs(kwargs['config'].response_schema, Metrics)
        self.assertEqual(kwargs['config'].response_mime_type, 'application/json')
        self.assertEqual(kwargs['config'].system_instruction, 'extract metrics')

    def test_empty_malformed_or_schema_invalid_response_fails(self):
        for text in (None, '', 'not json', '{}', '{"company":"Meta","impact_count":"many"}'):
            with self.subTest(text=text):
                self.client.models.generate_content.return_value = SimpleNamespace(text=text)
                with self.assertRaisesRegex(RuntimeError, 'structured output'):
                    self.service.generate_structured_output('story', Metrics)

    def test_sdk_failure_is_wrapped_with_cause_description(self):
        self.client.models.generate_content.side_effect = OSError('upstream disconnected')
        with self.assertRaisesRegex(RuntimeError, 'upstream disconnected'):
            self.service.generate_structured_output('story', Metrics)
