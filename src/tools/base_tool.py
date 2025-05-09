from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Type, TypeVar

from pydantic import BaseModel, ValidationError

from src.utils.logger import logger

ReqModel = TypeVar('ReqModel', bound=BaseModel)
RespModel = TypeVar('RespModel', bound=BaseModel)


class BaseTool(ABC, Generic[ReqModel, RespModel]):
    """
    Abstract base class for defining tools that an agent can use.

    Subclasses must define:
    - name: A unique string identifier for the tool.
    - description: A string describing what the tool does (used by LLM).
    - request_model: A Pydantic model defining the input schema for the tool.
    - response_model: A Pydantic model defining the output schema for the tool.
    And implement:
    - _handle: An async method containing the core logic of the tool.
    """
    # These attributes must be overridden by subclasses
    name: str
    description: str
    request_model: Type[ReqModel]
    response_model: Type[RespModel]

    @abstractmethod
    async def _handle(self, request: ReqModel) -> RespModel:
        """
        The core logic of the tool.
        This method receives a validated Pydantic model instance of `self.request_model`
        and must return a Pydantic model instance of `self.response_model`.

        Args:
            request: An instance of `self.request_model` containing the tool's input.

        Returns:
            An instance of `self.response_model` containing the tool's output.
        """
        pass

    async def execute(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public method to execute the tool.
        It validates the input data against `self.request_model`, calls the `_handle`
        method with the validated request model, ensures the handler returns an instance
        of `self.response_model`, and then returns the output as a dictionary.

        Args:
            request_data: A dictionary containing the raw input data for the tool.

        Returns:
            A dictionary representing the serialized output from `self.response_model`.

        Raises:
            ValueError: If input validation fails.
            TypeError: If the _handle method does not return the expected response model type.
        """
        try:
            parsed_request = self.request_model(**request_data)
        except ValidationError as e:
            logger.error(f"Input validation failed for tool '{self.name}': {e.errors()}")
            raise ValueError(f"Invalid input for tool {self.name}: {e.errors()}") from e

        response_object = await self._handle(parsed_request)

        if not isinstance(response_object, self.response_model):
            err_msg = (
                f"Tool '{self.name}' handler did not return an instance of "
                f"{self.response_model.__name__}. Got {type(response_object).__name__} instead."
            )
            logger.error(err_msg)
            raise TypeError(err_msg)

        return response_object.model_dump()

    async def __call__(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Makes the tool instance callable.
        This allows the agent to directly call the tool instance, passing arguments
        as keyword arguments, which are then processed by the `execute` method.
        Example: `tool_instance(arg1=value1, arg2=value2)`

        Args:
            **kwargs: Keyword arguments representing the input data for the tool.

        Returns:
            A dictionary representing the serialized output from the tool.
        """
        return await self.execute(kwargs)

    def get_tool_schema(self) -> Dict[str, Any]:
        """
        Generates a schema definition for the tool, typically for use by an LLM
        to understand how to call the tool (e.g., OpenAI function calling schema).

        Returns:
            A dictionary representing the tool's schema.

        Raises:
            AttributeError: If the tool does not have a Pydantic request_model defined.
        """
        if not hasattr(self, 'request_model') or not issubclass(self.request_model, BaseModel):
            raise AttributeError(
                f"Tool '{self.name}' must have a Pydantic 'request_model' defined to generate a schema."
            )

        # Standard OpenAI function/tool schema format
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.request_model.model_json_schema(),
            },
        }