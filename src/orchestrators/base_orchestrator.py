import asyncio
from typing import Any, Dict, Optional

from typing_extensions import TypedDict

from src.agents.base_agent import BaseAgent
from src.chains.base_chain import BaseChain
from src.tools.base_tool import BaseTool
from src.utils.logger import logger

# from src.agents.models import AgentResponse


class BaseOrchestrator:
    def __init__(self):
        self._tool_registry: Dict[str, BaseTool] = {}  # Ideally Dict[str, BaseTool]
        self._chain_registry: Dict[str, BaseChain] = {}
        self._agent_registry: Dict[str, BaseAgent] = {} # Ideally Dict[str, BaseAgent]
        logger.info("BaseOrchestrator initialized with empty registries.")

    # --- Tool Registry Methods ---
    def register_tool(self, key: str, tool: Any):
        if key in self._tool_registry:
            logger.warning(f"Tool with key '{key}' already registered. Overwriting.")
        self._tool_registry[key] = tool
        logger.debug(f"Tool '{key}' registered: {type(tool)}")

    def get_tool(self, key: str) -> Any:
        tool = self._tool_registry.get(key)
        if not tool:
            logger.error(f"Tool with key '{key}' not found in registry.")
            raise KeyError(f"Tool '{key}' not found.")
        return tool

    # --- Agent Registry Methods ---
    def register_agent(self, key: str, agent: Any):
        if key in self._agent_registry:
            logger.warning(f"Agent with key '{key}' already registered. Overwriting.")
        self._agent_registry[key] = agent
        logger.debug(f"Agent '{key}' registered: {type(agent)}")

    def get_agent(self, key: str) -> Any:
        agent = self._agent_registry.get(key)
        if not agent:
            logger.error(f"Agent with key '{key}' not found in registry.")
            raise KeyError(f"Agent '{key}' not found.")
        return agent

    def register_chain(self, key: str, chain_instance: BaseChain):
        """
        Registers a chain definition.
        A chain can be a list of ChainStep objects for sequential execution,
        or a callable (e.g., an agent instance that has a `run` method).
        The chain_instance must be a subclass of BaseChain.
        """
        if not isinstance(chain_instance, BaseChain):
            raise TypeError(
                f"Chain for key '{key}' must be an instance of BaseChain. "
                f"Got {type(chain_instance)}."
            )
        if key in self._chain_registry:
            logger.warning(f"Chain with key '{key}' already registered. Overwriting.")

        self._chain_registry[key] = chain_instance
        logger.debug(f"Chain '{key}' registered: {chain_instance!r}")

    def get_chain(self, key: str) -> BaseChain:
        chain_instance = self._chain_registry.get(key)
        if not chain_instance:
            logger.error(f"Chain with key '{key}' not found in registry.")
            raise KeyError(f"Chain '{key}' not found.")
        return chain_instance

    async def execute_workflow(
        self,
        chain_key: str,
        initial_input: Any,
        conversation_id: Optional[str] = None,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Executes a registered workflow (chain).

        Args:
            chain_key: The key of the chain to execute.
            initial_input: The initial input for the first step of the chain.
            conversation_id: Optional conversation ID to be passed to agents.
            workflow_context: Optional dictionary to carry state across complex chains.
                              This is passed to the chain's execute method.

        Returns:
            The final output of the workflow.
        """
        logger.info(f"Executing workflow for chain '{chain_key}' with initial input: {str(initial_input)[:100]}...")
        chain_to_execute = self.get_chain(chain_key)  # Fetches a BaseChain instance

        if workflow_context is None:
            workflow_context = {}

        try:
            final_output = await chain_to_execute.execute(
                initial_input=initial_input,
                conversation_id=conversation_id,
                workflow_context=workflow_context
            )
            logger.info(f"Workflow for chain '{chain_key}' executed successfully. Final output: {str(final_output)[:100]}...")
            return final_output

        except Exception as e:
            logger.error(
                f"Error during workflow execution for chain '{chain_key}': {e}",
                exc_info=True,
            )
            raise  # Re-raise the exception