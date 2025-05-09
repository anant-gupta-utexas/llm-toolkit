from typing import Any, Dict, Optional
from uuid import uuid4

from src.agents.tool_agent import ToolAgent
from src.chains.base_chain import AgentAsChain
from src.config.constants import (
    AGENT_TOOL_ASSISTANT,
    CHAIN_TOOL_AGENT_WORKFLOW,
    TOOL_MULTIPLY,
    TOOL_RANDOM_NUMBER,
)
from src.memory.in_memory import InMemoryMemoryService
from src.observability.context import get_conversation_id
from src.observability.decorators import trace_external_call
from src.orchestrators.base_orchestrator import BaseOrchestrator
from src.providers.gemini_client import GeminiClient
from src.tools.multiply import MultiplyTool
from src.tools.random_number import RandomNumberTool
from src.utils.logger import logger


class ToolAgentWorkflowOrchestrator(BaseOrchestrator):
    """
    An orchestrator specifically designed to run a workflow involving a ToolAgent.
    It initializes and registers the necessary tools, the agent, and the chain.
    """

    def __init__(self, llm_client=None, memory_service=None):
        super().__init__()
        self.llm_client = llm_client or GeminiClient()
        self.memory_service = memory_service or InMemoryMemoryService()
        self._initialize_workflow_components()

    def _initialize_workflow_components(self):
        logger.info("Initializing components for ToolAgentWorkflowOrchestrator...")

        # Instantiate and Register Tools
        multiply_tool = MultiplyTool()
        self.register_tool(TOOL_MULTIPLY, multiply_tool)

        random_tool = RandomNumberTool()
        self.register_tool(TOOL_RANDOM_NUMBER, random_tool)

        # Instantiate and Register Agent
        agent_tools_map = {
            multiply_tool.name: multiply_tool,
            random_tool.name: random_tool,
        }
        tool_agent_instance = ToolAgent(
            llm_client=self.llm_client,
            agent_name="ToolAgent",
            tools=agent_tools_map,
            memory_service=self.memory_service,
            enable_tracing=True,
            max_tool_concurrency=3,
        )
        self.register_agent(AGENT_TOOL_ASSISTANT, tool_agent_instance)

        # Instantiate and Register Chain
        agent_workflow_chain = AgentAsChain(
            chain_key=CHAIN_TOOL_AGENT_WORKFLOW,
            orchestrator=self,  # Pass self (the orchestrator instance)
            agent_key=AGENT_TOOL_ASSISTANT,
        )
        self.register_chain(CHAIN_TOOL_AGENT_WORKFLOW, agent_workflow_chain)
        logger.info(
            "ToolAgentWorkflowOrchestrator initialized and components registered."
        )

    @trace_external_call("tool_agent_workflow_orchestrator.handle_user_message")
    async def handle_user_message(
        self, user_message: str, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        effective_conv_id = (
            conversation_id or get_conversation_id() or f"orch-fallback-{uuid4()}"
        )
        logger.info(
            f"Handling message for conversation: {effective_conv_id} via ToolAgentWorkflowOrchestrator"
        )

        response_content = await self.execute_workflow(
            chain_key=CHAIN_TOOL_AGENT_WORKFLOW,
            initial_input=user_message,
            conversation_id=effective_conv_id,
        )

        logger.info(
            f"Workflow finished for conversation: {effective_conv_id}. Response: {str(response_content)[:100]}..."
        )
        return {"agent_response": response_content}
