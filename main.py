from src.utils.logger import logger
from src.workflows.my_workflow import MyWorkflow


def main():
    logger.info("Starting the LLM application")
    workflow = MyWorkflow()
    task = "What is the capital of France? and what is 465 times 321 then add 95297 and then divide by 13.2?"
    result = workflow.run_task(task)
    if result:
        logger.info(f"Task result: {result}")
    else:
        logger.error("Task failed")


if __name__ == "__main__":
    main()
