from app.features.feed.data.model.company_layoff_extraction import CompanyLayoffExtraction
from app.services.gemini.base_gemini_service import BaseGeminiService


class FeedIngestionService:
    """
    Feature-level coordinator that manages text cleaning pipelines and
    calls our shared Gemini infrastructure engine.
    """

    def __init__(self):
        # Instantiate our shared engine wrapper
        self.ai_engine = BaseGeminiService()

    def process_raw_story(self, raw_input_text: str) -> CompanyLayoffExtraction:
        """
        Cleans and normalizes raw text payloads by piping parameters to the base AI system.
        """
        # 1. Perform any manual regex scrubbing or formatting cleanup here first if needed
        sanitized_text = raw_input_text.strip()

        # 2. Define custom domain constraints
        instruction = (
            "You are an elite corporate workforce intelligence tool. Isolate precise corporate "
            "layoff events from the material. Map unverified alerts strictly to 'Rumored'."
        )

        prompt = f"Analyze the following data input and extract metrics: \n{sanitized_text}"

        # 3. Trigger the base class handler, requesting our specific feed schema format
        extracted_result = self.ai_engine.generate_structured_output(
            prompt=prompt,
            response_schema=CompanyLayoffExtraction,
            system_instruction=instruction
        )

        return extracted_result