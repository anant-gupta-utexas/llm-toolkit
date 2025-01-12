import os

from adalflow.core.model_client import ModelClient
from adalflow.core.types import GeneratorOutput, ModelType
from google import genai
from google.genai import types

from src.config.constants import GEMINI_20_FLASH
from src.utils.config_loader import ConfigLoader


class GeminiClient(ModelClient):
    def __init__(self):
        super().__init__()
        self.configs = ConfigLoader().get_configs()
        # Initialize the google-genai client
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def convert_inputs_to_api_kwargs(
        self, input, model_kwargs={}, model_type=ModelType.UNDEFINED
    ):
        if model_type == ModelType.LLM:
            config = types.GenerateContentConfig(
                temperature=model_kwargs.get("temperature"),
                max_output_tokens=model_kwargs.get("max_output_tokens"),
            )
            return {
                "model": self.configs[GEMINI_20_FLASH]["model"],
                "contents": input,
                "config": config.__dict__,  # Convert to dict
            }
        else:
            raise ValueError(f"model_type {model_type} is not supported")

    def call(self, api_kwargs={}, model_type=ModelType.UNDEFINED):
        if model_type == ModelType.LLM:
            try:
                response = self.client.models.generate_content(**api_kwargs)
                return response
            except Exception as e:
                print(f"Gemini API Error: {e}")
                return None
        else:
            raise ValueError(f"model_type {model_type} is not supported")

    def parse_chat_completion(self, response):
        if response and response.text:
            return GeneratorOutput(
                data=response.text, error=None, raw_response=str(response)
            )
        else:
            return GeneratorOutput(
                data=None,
                error="No text in Gemini response",
                raw_response=str(response),
            )
