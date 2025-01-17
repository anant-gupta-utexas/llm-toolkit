import json
from typing import Any, Dict, List, Optional

from adalflow.core.model_client import ModelClient
from adalflow.core.types import EmbedderOutput, GeneratorOutput, ModelType
from ollama import Client, GenerateResponse

from src.config.constants import LLAMA_32
from src.utils.config_loader import ConfigLoader


class OllamaClient(ModelClient):
    def __init__(self):
        super().__init__()
        self.configs = ConfigLoader().get_configs()
        self.host = self.configs[LLAMA_32]["host"]
        self._sync_client = None
        self._async_client = None

    def init_sync_client(self):
        """Create the synchronous client."""
        if not self._sync_client:
            self._sync_client = Client(host=self.host)
        return self._sync_client

    def init_async_client(self):
        """Create the asynchronous client."""
        if not self._async_client:
            self._async_client = Client(host=self.host)
        return self._async_client

    def parse_chat_completion(
        self, completion: GenerateResponse | str
    ) -> GeneratorOutput:
        """Parse the completion to a str. We use the generate with prompt instead of chat with messages."""

        if isinstance(completion, str):
            try:
                json_string = (
                    completion.replace("```json", "").replace("```", "").strip()
                )
                json_data = json.loads(json_string)
                return GeneratorOutput(
                    data=json_data, error=None, raw_response=str(completion)
                )
            except json.JSONDecodeError as e:
                return GeneratorOutput(
                    data=None,
                    error=f"JSON Decode Error: {e}",
                    raw_response=str(completion),
                )
        elif isinstance(completion, GenerateResponse):
            try:
                # return completion.response
                return GeneratorOutput(
                    data="",
                    error=None,
                    raw_response=completion.response,
                )
            except Exception as e:
                return GeneratorOutput(
                    data=None,
                    error=f"Error parsing response {e}",
                    raw_response=str(completion),
                )
        else:
            return GeneratorOutput(
                data=None, error="Invalid completion type", raw_response=str(completion)
            )

    def parse_embedding_response(
        self, response: Dict[str, List[float]]
    ) -> EmbedderOutput:
        """Parse the embedding response to a structure LightRAG components can understand."""
        try:
            embedding = response.get("embedding")
            if embedding:
                return EmbedderOutput(data=embedding, error=None)
            else:
                return EmbedderOutput(
                    data=None, error="No embeddings found in response"
                )
        except Exception as e:
            return EmbedderOutput(
                data=None, error=f"Error parsing embedding response {e}"
            )

    def convert_inputs_to_api_kwargs(
        self,
        input: Any = None,
        model_kwargs: Dict = {},
        model_type: ModelType = ModelType.UNDEFINED,
    ) -> Dict:
        """Convert the input and model_kwargs to api_kwargs for the Ollama SDK client."""
        api_kwargs = {}

        if model_type == ModelType.LLM:
            api_kwargs["prompt"] = input
            api_kwargs["model_kwargs"] = model_kwargs

        elif model_type == ModelType.EMBEDDER:
            api_kwargs["prompt"] = model_kwargs.get("prompt", input)
            api_kwargs.update(model_kwargs.get("options", {}))

        return api_kwargs

    def call(self, api_kwargs={}, model_type=ModelType.UNDEFINED):
        client = self.init_sync_client()
        try:
            if model_type == ModelType.LLM:
                completion = client.generate(
                    prompt=api_kwargs["prompt"],
                    model=api_kwargs["model_kwargs"]["model"],
                )
                return completion

            elif model_type == ModelType.EMBEDDER:
                response = client.embeddings(**api_kwargs)
                return self.parse_embedding_response(response)
            else:
                return GeneratorOutput(
                    data=None, error="Invalid model_type", raw_response=str(api_kwargs)
                )
        except Exception as e:
            return GeneratorOutput(
                data=None,
                error=f"Error calling Ollama API {e}",
                raw_response=str(api_kwargs),
            )

    async def acall(
        self, api_kwargs: Dict = {}, model_type: ModelType = ModelType.UNDEFINED
    ) -> GeneratorOutput | EmbedderOutput:
        """Subclass use this to call the API with the async client."""
        client = self.init_async_client()
        try:
            if model_type == ModelType.LLM:
                completion = await client.generate(**api_kwargs)
                return self.parse_generate_response(completion)
            elif model_type == ModelType.EMBEDDER:
                response = await client.embeddings(**api_kwargs)
                return self.parse_embedding_response(response)
            else:
                return GeneratorOutput(
                    data=None, error="Invalid model_type", raw_response=str(api_kwargs)
                )
        except Exception as e:
            return GeneratorOutput(
                data=None,
                error=f"Error calling async Ollama API {e}",
                raw_response=str(api_kwargs),
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OllamaClient":
        """Create an instance from previously serialized data using to_dict() method."""
        return cls(**data)

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert the component to a dictionary."""
        return {"host": self.host}
