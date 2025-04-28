from uuid import uuid4

from src.agents.my_agent import MyAgent
from src.chains.gemini_qa import GeminiQA
from src.chains.ollama_qa import OllamaQA
from src.observability.decorators import trace_external_call
from src.utils.logger import logger


@trace_external_call("api_orchestrator")
def ApiOrchestrator():
    logger.info("Starting the LLM application")
    gemini_task = GeminiQA()
    ollama_task = OllamaQA()
    agent = MyAgent()
    task = "Helloooo from Mars"
    result = gemini_task.call(query=task, id=str(uuid4))
    response = agent(
        "I want to multiply 3 and 4. Also, what is capital of France", id="123"
    )
    if result:
        logger.info(f"Task result: {result}")
    else:
        logger.error("Task failed")

    return {"chain_response": result, "agent_response": response.answer}