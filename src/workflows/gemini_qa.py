from adalflow.core import Component, Generator

from src.config.constants import GEMINI_20_FLASH
from src.models.gemini_client import GeminiClient
from src.utils.config_loader import ConfigLoader

template_doc = r"""<SYS> You are a doctor </SYS> User: {{input_str}}"""


class GeminiQA(Component):
    def __init__(self):
        super().__init__()
        self.configs = ConfigLoader().get_configs()
        self.doc = Generator(
            template=template_doc,
            model_client=GeminiClient(),
            model_kwargs=self.configs[GEMINI_20_FLASH],
        )

    def call(self, query: str) -> str:
        return self.doc(prompt_kwargs={"input_str": query}).data
