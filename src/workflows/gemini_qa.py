from adalflow.core import Component, Generator
from adalflow.tracing import trace_generator_call, trace_generator_states

from src.config.constants import GEMINI_20_FLASH
from src.models.gemini_client import GeminiClient
from src.utils.config_loader import Config

template_doc = r"""<SYS> You are a doctor </SYS> User: {{input_str}}"""

@trace_generator_states()
@trace_generator_call(error_only=False)
class GeminiQA(Component):
    def __init__(self):
        super().__init__()
        self.doc = Generator(
            template=template_doc,
            model_client=GeminiClient(),
            model_kwargs=Config[GEMINI_20_FLASH],
        )

    def call(self, query: str) -> str:
        response = self.doc(prompt_kwargs={"input_str": query})
        return response.data
