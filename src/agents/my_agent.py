from typing import Optional, Union

from adalflow.components.agent import ReActAgent
from adalflow.components.output_parsers import JsonOutputParser
from adalflow.core import Component, Generator
from adalflow.core.func_tool import AsyncCallable, FunctionTool
from adalflow.core.tool_manager import ToolManager
from adalflow.core.types import Function, FunctionOutput, GeneratorOutput, StepOutput
from adalflow.optim.parameter import Parameter, ParameterType
from adalflow.tracing import trace_generator_call, trace_generator_states

from src.config.constants import GEMINI_20_FLASH, LLAMA_32
from src.providers.gemini_client import GeminiClient
from src.providers.ollama_client import OllamaClient
from src.utils.config_loader import Config
from src.utils.logger import logger


# Define tools
def multiply(a: int, b: int) -> int:
    """
    Multiply two numbers.
    """
    return a * b


def add(a: int, b: int) -> int:
    """
    Add two numbers.
    """
    return a + b


def divide(a: float, b: float) -> float:
    """
    Divide two numbers.
    """
    return float(a) / b

@trace_generator_states()
@trace_generator_call(error_only=False)
class MyAgent(Component):
    def __init__(self):
        super().__init__()
        self.model_client = GeminiClient()
        self.llm_tool = Generator(
            model_client=OllamaClient(),
            model_kwargs=Config[LLAMA_32],
        )

        def llm_as_tool(input: str, id: Optional[str] = None) -> str:
            """Used as a calculator tool."""
            logger.info(f"llm_as_tool: {input}", color="yellow")

            return self.llm_tool(prompt_kwargs={"input_str": input}, id=id)

        self.agent = ReActAgent(
            tools=[FunctionTool(llm_as_tool, component=self.llm_tool)],
            model_client=self.model_client,
            model_kwargs=Config[GEMINI_20_FLASH],
            max_steps=2,
            add_llm_as_fallback=False,
        )

    def call(self, input: str, id: Optional[str] = None) -> Union[str, "Parameter"]:
            response = self.agent(input, id=id)
            return response


    def run(self, task):
        try:
            logger.info(f"Starting task: {task}")
            response = self.agent.call(input=task)
            logger.info(f"Agent response: {response}")
            return response
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None
