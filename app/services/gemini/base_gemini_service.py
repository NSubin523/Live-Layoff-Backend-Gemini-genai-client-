from typing import TypeVar, Type

from google import genai
from google.genai import types
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)
base_system_instruction = "You are a precise data extraction intelligence."

class BaseGeminiService:

    def __init__(self, model_name: str = 'gemini-2.5-flash'):
        self.client = genai.Client()
        self.model_name = model_name

    def generate_structured_output(
            self,
            prompt: str,
            response_schema: Type[T],
            system_instruction: str = base_system_instruction
    ) -> T:
        try:
            response = self.client.models.generate_content(
                model = self.model_name,
                contents = prompt,
                config = types.GenerateContentConfig(
                    system_instruction = system_instruction,
                    response_mime_type = "application/json",
                    response_schema = response_schema,
                    temperature = 0.0
                )
            )

            if not response.text:
                raise ValueError("The Gemini API returned an empty or invalid generation response.")

            return response_schema.model_validate_json(response.text)

        except Exception as e:
            raise RuntimeError(f"An error occured while generating the structured output: {e}")