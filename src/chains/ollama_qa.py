from adalflow.core import Component, Generator

from src.config.constants import LLAMA_32
from src.providers.ollama_client import OllamaClient
from src.utils.config_loader import Config

template_doc = r"""<SYS> You are a philosopher </SYS> User: {{input_str}}"""


class OllamaQA(Component):
    def __init__(self):
        super().__init__()
        model_config = Config[LLAMA_32].copy()
        model_config.pop("host", None)

        self.doc = Generator(
            template=template_doc,
            model_client=OllamaClient(),
            model_kwargs=model_config,
        )

    def call(self, query: str) -> str:
        response = self.doc(prompt_kwargs={"input_str": query})
        return response.data
