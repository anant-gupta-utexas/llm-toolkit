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

from src.providers.models import (
    Content,
    FunctionCall,
    FunctionCallPart,
    FunctionResponse,
    FunctionResponsePart,
    ImagePart,
    MessageInput,
    PartType,
    TextPart,
)
from src.utils.logger import logger
from src.utils.timer import timer


class GeminiClient(ModelClient):
    def __init__(self):
        super().__init__()
        # Initialize the google-genai client
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def build_messages(inputs: List[MessageInput]) -> List[Content]:
        """
        Build messages from various input types for the Gemini API.

        Args:
            inputs: List of MessageInput objects containing text, image, function calls, etc.

        Returns:
            List of Content objects formatted for the Gemini API.
        """
        contents = []
        current_content = None

        for input_item in inputs:
            # Create a new Content object if the role changes
            if not current_content or current_content.role != input_item.role:
                if current_content:
                    contents.append(current_content)

                current_content = Content(role=input_item.role, parts=[])

            # Add parts based on the input type
            if input_item.text:
                current_content.parts.append(TextPart(text=input_item.text))

            if input_item.image_uri and input_item.image_mime_type:
                current_content.parts.append(
                    ImagePart(
                        uri=input_item.image_uri,
                        mime_type=input_item.image_mime_type
                    )
                )

            if input_item.function_call:
                current_content.parts.append(
                    FunctionCallPart(
                        function_call=input_item.function_call
                    )
                )

            if input_item.function_response:
                current_content.parts.append(
                    FunctionResponsePart(
                        function_response=input_item.function_response
                    )
                )

        # Add the last content if it exists
        if current_content:
            contents.append(current_content)

        return contents

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