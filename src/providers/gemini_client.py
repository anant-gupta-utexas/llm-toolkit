import json
import os

from adalflow.core.model_client import ModelClient
from adalflow.core.types import CompletionUsage, GeneratorOutput, ModelType
from google import genai
from google.genai.types import GenerateContentConfig, GenerateContentResponse

from src.utils.logger import logger
from src.utils.timer import timer


class GeminiClient(ModelClient):
    def __init__(self):
        super().__init__()
        # Initialize the google-genai client
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def convert_inputs_to_api_kwargs(
        self, input, model_kwargs={}, model_type=ModelType.UNDEFINED
    ):
        if model_type == ModelType.LLM:
            config = GenerateContentConfig(
                temperature=model_kwargs.get("temperature"),
                max_output_tokens=model_kwargs.get("max_output_tokens"),
            )
            return {
                "model": model_kwargs.get("model"),
                "contents": input,
                "config": config.__dict__,  # Convert to dict
            }
        else:
            raise ValueError(f"model_type {model_type} is not supported")
    @timer
    def call(self, api_kwargs={}, model_type=ModelType.UNDEFINED):
        if model_type == ModelType.LLM:
            try:
                response = self.client.models.generate_content(**api_kwargs)
                return response
            except Exception as e:
                logger.error(f"Gemini API Error: {e}")
                return None
        else:
            raise ValueError(f"model_type {model_type} is not supported")

    def parse_chat_completion(
        self, completion: GenerateContentResponse
    ) -> "GeneratorOutput":
        """
        Parse the completion to a structure your sytem standarizes. (here is str)
        """
        logger.debug(f"completion: {completion}")
        try:
            data = completion.text
            usage = self.track_completion_usage(completion)
            return GeneratorOutput(
                data=None, usage=usage, raw_response=data, metadata={"model": completion.model_version}
            )
        except Exception as e:
            logger.error(f"Error parsing completion: {e}")
            return GeneratorOutput(
                data=None, error=str(e), raw_response=str(completion)
            )

    def track_completion_usage(
        self, completion: GenerateContentResponse
    ) -> CompletionUsage:
        return CompletionUsage(
            completion_tokens=completion.usage_metadata.candidates_token_count,
            prompt_tokens=completion.usage_metadata.prompt_token_count,
            total_tokens=completion.usage_metadata.total_token_count,
        )