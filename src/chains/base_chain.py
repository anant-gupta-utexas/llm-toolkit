import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypedDict

from src.utils.logger import logger

# Forward declaration for BaseOrchestrator to avoid circular import issues
# when BaseOrchestrator is type hinted in __init__.
if TYPE_CHECKING:
    from src.orchestrators.base_orchestrator import BaseOrchestrator


class ChainStep(TypedDict, total=False):
    """
    Defines a single step within a SequentialStepChain.
    - type: "tool" or "agent".
    - key: The registration key for the tool or agent in the orchestrator.
    - input_key: (Optional) The key in the workflow_context from which to read this step's input.
                 Defaults to "_last_step_output" which carries the output of the previous step.
    - output_key: (Optional) The key in the workflow_context where this step's output will be stored.
                  Defaults to "_last_step_output", making it available for the next step.
    """

    type: str
    key: str
    input_key: Optional[str]
    output_key: Optional[str]


class BaseChain(ABC):
    """
    Abstract base class for all chains.
    A chain defines a sequence or graph of operations (tools, agents)
    to achieve a larger goal.
    """

    def __init__(self, chain_key: str, orchestrator: "BaseOrchestrator"):
        self.chain_key = chain_key
        self.orchestrator = orchestrator  # Provides access to tool/agent registries
        self.logger = (
            logger  # Use the shared logger, or instantiate a chain-specific one
        )

    @abstractmethod
    async def execute(
        self,
        initial_input: Any,
        conversation_id: Optional[str] = None,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Executes the chain's logic.

        Args:
            initial_input: The initial input for the chain.
            conversation_id: Optional conversation ID for context.
            workflow_context: A dictionary to pass and manage state between steps
                              within the chain. The chain implementation is responsible
                              for how it uses this context.

        Returns:
            The final output of the chain.
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}(chain_key='{self.chain_key}')>"


class SequentialStepChain(BaseChain):
    """
    A chain that executes a predefined sequence of tool or agent steps.
    It uses a workflow_context to pass data between steps.
    """

    def __init__(
        self, chain_key: str, orchestrator: "BaseOrchestrator", steps: List[ChainStep]
    ):
        super().__init__(chain_key, orchestrator)
        if not steps:
            raise ValueError(
                "SequentialStepChain must be initialized with at least one step."
            )
        self.steps = steps

    async def execute(
        self,
        initial_input: Any,
        conversation_id: Optional[str] = None,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        self.logger.info(
            f"Executing SequentialStepChain '{self.chain_key}' with {len(self.steps)} steps."
        )
        if workflow_context is None:
            workflow_context = {}

        # Prime the context with the initial input, using a default key.
        # The first step can then pick this up if its input_key matches or is default.
        workflow_context["_initial_chain_input"] = initial_input
        # Default key for carrying over output from one step to the next
        workflow_context["_last_step_output"] = initial_input

        final_output_key = "_last_step_output"  # Default if not overridden by last step

        for i, step_config in enumerate(self.steps):
            step_type = step_config.get("type")
            step_key = step_config.get("key")

            # Determine input source: use specified input_key or default to previous step's output
            input_context_key = step_config.get("input_key")
            if input_context_key is None:  # Default behavior
                if i == 0:  # First step
                    current_step_input = workflow_context["_initial_chain_input"]
                else:  # Subsequent steps
                    current_step_input = workflow_context["_last_step_output"]
            elif input_context_key in workflow_context:
                current_step_input = workflow_context[input_context_key]
            else:
                err_msg = (
                    f"Input key '{input_context_key}' not found in workflow_context for step {i + 1} "
                    f"(type: {step_type}, key: {step_key}) in chain '{self.chain_key}'. "
                    f"Available keys: {list(workflow_context.keys())}"
                )
                self.logger.error(err_msg)
                raise KeyError(err_msg)

            # Determine output destination: use specified output_key or default
            output_context_key = step_config.get("output_key", "_last_step_output")
            final_output_key = output_context_key  # The output of the last executed step will be the chain's output

            if not step_type or not step_key:
                self.logger.error(
                    f"Invalid step configuration in chain '{self.chain_key}', step {i + 1}: {step_config}"
                )
                raise ValueError(
                    f"Invalid step in chain '{self.chain_key}': missing type or key."
                )

            self.logger.info(
                f"Executing step {i + 1}/{len(self.steps)}: Type='{step_type}', Key='{step_key}', "
                f"InputFrom='{input_context_key or ('_initial_chain_input' if i == 0 else '_last_step_output')}', "
                f"OutputTo='{output_context_key}'"
            )
            step_output = None

            if step_type == "agent":
                agent_to_run = self.orchestrator.get_agent(step_key)
                if not isinstance(current_step_input, str):
                    self.logger.warning(
                        f"Agent step '{step_key}' expects string input, got {type(current_step_input)}. Converting."
                    )
                    input_for_agent = str(current_step_input)
                else:
                    input_for_agent = current_step_input

                agent_response = await agent_to_run.run(
                    user_input=input_for_agent, conversation_id=conversation_id
                )
                step_output = (
                    agent_response.output
                    if hasattr(agent_response, "output")
                    else agent_response
                )
                self.logger.debug(
                    f"Agent '{step_key}' executed. Output: {str(step_output)[:100]}..."
                )

            elif step_type == "tool":
                tool_to_run = self.orchestrator.get_tool(step_key)
                if not isinstance(current_step_input, dict):
                    err_msg = (
                        f"Tool step '{step_key}' expects a dictionary of arguments, "
                        f"but current input (from '{input_context_key}') is of type {type(current_step_input)}: '{str(current_step_input)[:100]}'"
                    )
                    self.logger.error(err_msg)
                    raise ValueError(err_msg)

                if not callable(tool_to_run):  # BaseTool instances are callable
                    err_msg = f"Tool '{step_key}' (type: {type(tool_to_run)}) retrieved from registry is not callable."
                    self.logger.error(err_msg)
                    raise TypeError(err_msg)

                step_output = await tool_to_run(
                    **current_step_input
                )  # Assumes BaseTool's __call__
                self.logger.debug(
                    f"Tool '{step_key}' executed. Output: {str(step_output)[:100]}..."
                )

            else:
                self.logger.error(
                    f"Unknown step type '{step_type}' in chain '{self.chain_key}'."
                )
                raise ValueError(
                    f"Unknown step type '{step_type}' in chain '{self.chain_key}'."
                )

            workflow_context[output_context_key] = step_output
            if (
                output_context_key != "_last_step_output"
            ):  # Ensure _last_step_output is also updated for default chaining
                workflow_context["_last_step_output"] = step_output

        final_output = workflow_context.get(final_output_key)
        self.logger.info(
            f"SequentialStepChain '{self.chain_key}' finished. Final output from '{final_output_key}': {str(final_output)[:100]}..."
        )
        return final_output


class AgentAsChain(BaseChain):
    """
    A chain that wraps a single registered agent, making it executable
    as a chain workflow.
    """

    def __init__(
        self, chain_key: str, orchestrator: "BaseOrchestrator", agent_key: str
    ):
        super().__init__(chain_key, orchestrator)
        self.agent_key = agent_key
        # Eagerly get the agent to fail fast if not registered or invalid
        self._agent_instance = self.orchestrator.get_agent(self.agent_key)
        if not (
            hasattr(self._agent_instance, "run")
            and asyncio.iscoroutinefunction(getattr(self._agent_instance, "run"))
        ):
            raise TypeError(
                f"Agent '{agent_key}' (type: {type(self._agent_instance)}) for AgentAsChain '{chain_key}' "
                "does not have a callable async 'run' method."
            )

    async def execute(
        self,
        initial_input: Any,
        conversation_id: Optional[str] = None,
        workflow_context: Optional[
            Dict[str, Any]
        ] = None,  # workflow_context is generally not used by this simple chain
    ) -> Any:
        self.logger.info(
            f"Executing AgentAsChain '{self.chain_key}' using agent '{self.agent_key}'."
        )

        if not isinstance(initial_input, str):
            self.logger.warning(
                f"Agent execution for chain '{self.chain_key}' (agent '{self.agent_key}') expects string input, "
                f"got {type(initial_input)}. Converting to string: '{str(initial_input)[:100]}'"
            )
            input_for_agent = str(initial_input)
        else:
            input_for_agent = initial_input

        agent_response = await self._agent_instance.run(
            user_input=input_for_agent, conversation_id=conversation_id
        )
        # Assuming AgentResponse has an 'output' attribute for the final text response
        final_output = (
            agent_response.output
            if hasattr(agent_response, "output")
            else agent_response
        )
        self.logger.info(
            f"AgentAsChain '{self.chain_key}' executed. Final output: {str(final_output)[:100]}..."
        )
        return final_output
