from src.utils.logger import logger
from src.workflows.gemini_qa import GeminiQA
from src.workflows.ollama_qa import OllamaQA


def main():
    logger.info("Starting the LLM application")
    gemini_task = GeminiQA()
    ollam_task = OllamaQA()
    task = "Helloooo from Mars"
    result = ollam_task.call(query=task)
    if result:
        logger.info(f"Task result: {result}")
    else:
        logger.error("Task failed")


if __name__ == "__main__":
    main()
