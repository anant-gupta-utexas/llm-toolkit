from adalflow.components.agent import ReActAgent

from src.config.constants import GEMINI_20_FLASH
from src.models.gemini_client import GeminiClient
from src.utils.config_loader import ConfigLoader
from src.utils.logger import logger


class MyAgent:
    def __init__(self):
        self.configs = ConfigLoader().get_configs()
        self.tools = []  # Add the tools your agent will use here
        self.model_client = GeminiClient()
        self.agent = ReActAgent(
            # tools=self.tools,
            model_client=self.model_client,  # Use the gemini client
            model_kwargs=self.configs[GEMINI_20_FLASH],  # Use gemini config
            max_steps=2,
            add_llm_as_fallback=False,
        )

    def run(self, task):
        try:
            logger.info(f"Starting task: {task}")
            response = self.agent.call(input=task)
            logger.info(f"Agent response: {response}")
            return response
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None
