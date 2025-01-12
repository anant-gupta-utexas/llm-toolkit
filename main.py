from src.utils.logger import logger
from workflows.doc_qa import DocQA


def main():
    logger.info("Starting the LLM application")
    workflow = DocQA()
    task = "What is the treatment for severe headaches"
    result = workflow(task)
    if result:
        logger.info(f"Task result: {result}")
    else:
        logger.error("Task failed")


if __name__ == "__main__":
    main()
