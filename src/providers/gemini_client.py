import json
import os
from typing import Any, Dict, List, Optional

from adalflow.core.model_client import ModelClient
from adalflow.core.types import CompletionUsage, GeneratorOutput, ModelType
from google import genai
from google.genai.types import (
    ContentDict,
    GenerateContentConfig,
    GenerateContentResponse,
    Tool,
)

from src.utils.logger import logger
from src.utils.timer import timer


class GeminiClient(ModelClient):
    def __init__(self):
        super().__init__()
        # Initialize the google-genai client
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def build_messages(
        self,
        user_message: str,
        history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> List[ContentDict]:
        """
        Builds the message list in the format required by the Gemini API.

        Args:
            user_message: The latest message from the user.
            history: The existing conversation history (list of {'role': str, 'content': str}).
            system_prompt: An optional system prompt to prepend.

        Returns:
            A list of ContentDict suitable for the Gemini API 'contents' parameter.
        """
        gemini_messages: List[ContentDict] = []

        # Gemini doesn't have a dedicated 'system' role like OpenAI.
        # We often prepend system instructions as the first 'user' message
        # followed by an empty 'model' response, or include it in the first user turn.
        # Let's prepend it if provided.
        if system_prompt:
             # Simple approach: add as first user message
             gemini_messages.append({'role': 'user', 'parts': [system_prompt]})
             # Gemini requires alternating user/model roles, add dummy model response
             gemini_messages.append({'role': 'model', 'parts': ["Okay, I understand the instructions."]})

        for msg in history:
            gemini_messages.append({'role': msg['role'], 'parts': [msg['content']]})

        gemini_messages.append({'role': 'user', 'parts': [user_message]})
        return gemini_messages

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
                # TODO: Handle tools based on documentation
                # "tools": model_kwargs.get("tools") # Pass tools if provided
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