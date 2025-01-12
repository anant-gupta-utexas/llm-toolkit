from src.agents.my_agent import MyAgent
from src.utils.logger import logger


class NewWorkflow:
    def __init__(self):
        self.agent = MyAgent()

    def run_task(self, task):
        try:
            logger.info(f"Starting workflow with task {task}")
            result = self.agent.run(task)
            logger.info(f"Workflow completed with result {result}")
            return result
        except Exception as e:
            logger.error(f"Error in workflow {e}")
            return None
