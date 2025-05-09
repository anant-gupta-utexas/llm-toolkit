# LLM Toolkit

This repository contains all the basic elements to construct effective LLM tasks, providing a modular and extensible framework for building sophisticated AI applications. It includes components for agent creation, tool usage, workflow orchestration, conversation memory, and observability.

## Table of Contents

*   [Core Concepts & Architecture](#core-concepts--architecture)
    *   [Orchestrators](#orchestrators)
    *   [Agents](#agents)
    *   [Tools](#tools)
    *   [Chains](#chains)
    *   [Providers](#providers)
    *   [Memory](#memory)
    *   [Observability](#observability)
    *   [Constants](#constants)
*   [Project Structure](#project-structure)
*   [Setup and Installation](#setup-and-installation)
    *   [Prerequisites](#prerequisites)
    *   [Cloning the Repository](#cloning-the-repository)
    *   [Setting up Virtual Environment](#setting-up-virtual-environment)
    *   [Installing Dependencies](#installing-dependencies)
    *   [Environment Variables](#environment-variables)
*   [Running the Application](#running-the-application)
*   [How to Extend](#how-to-extend)
    *   [Adding New Tools](#adding-new-tools)
    *   [Adding New Agents](#adding-new-agents)
    *   [Adding New Chains](#adding-new-chains)
*   [Contributing](#contributing)
*   [License](#license)

## Core Concepts & Architecture

The toolkit is designed around several key abstractions that work together:

### Orchestrators

Orchestrators are responsible for managing and executing complex workflows.

*   **`BaseOrchestrator` (`src/orchestrators/base_orchestrator.py`)**:
    *   Acts as a central registry for tools, agents, and chains.
    *   Provides a generic `execute_workflow` method to run registered chains.
    *   Allows for decoupling of workflow definition from execution.
*   **`ToolAgentWorkflowOrchestrator` (`src/orchestrators/app_orchestrators.py`)**:
    *   A concrete implementation inheriting from `BaseOrchestrator`.
    *   Specifically designed to set up and run a workflow involving the `ToolAgent`.
    *   Initializes and registers necessary tools, the `ToolAgent`, and an `AgentAsChain` that uses this agent.
    *   Exposes a `handle_user_message` method, likely used by API endpoints, to process user input through the defined agent workflow.

### Agents

Agents are entities that can reason, use tools, and interact with LLMs to accomplish tasks.

*   **`BaseAgent` (`src/agents/base_agent.py`)**:
    *   An abstract base class defining the core functionalities of an agent.
    *   Handles LLM interaction via an `adalflow.core.Generator` and a specified `ModelClient` (e.g., `GeminiClient`).
    *   Manages conversation history, optionally integrating with a `BaseMemory` service.
    *   Provides methods for parsing tool arguments (`parse_tool_arguments`) and running tools (`_run_tool`, `process_tool_calls`, `process_tool_calls_concurrent`).
    *   Integrates with OpenTelemetry for tracing, creating spans for agent runs, LLM calls, tool parsing, and tool execution. Common span attributes like `conversation_id` and LLM model name are automatically added.
    *   Requires subclasses to implement the `_agent_loop` method.
*   **`ToolAgent` (`src/agents/tool_agent.py`)**:
    *   A concrete implementation of `BaseAgent`.
    *   Its `_agent_loop` method defines a cycle of:
        1.  Calling the LLM with the current conversation history.
        2.  Parsing the LLM response for potential tool calls.
        3.  If tool calls are present, executing them (sequentially or concurrently based on `max_tool_concurrency`).
        4.  Adding tool results back to the conversation history.
        5.  Repeating the cycle or returning a final response if no tool calls are made or `max_iterations` is reached.

### Tools

Tools are specific functions or capabilities that an agent can use to interact with the external world or perform specific computations.

*   **`BaseTool` (`src/tools/base_tool.py`)**:
    *   An abstract base class providing a standardized way to define tools.
    *   Requires subclasses to define `name`, `description`, Pydantic models for `request_model` and `response_model`, and implement an async `_handle` method for the core logic.
    *   Includes an `execute` method that handles input validation (against `request_model`) and output serialization.
    *   Implements `__call__` to make tool instances directly callable.
    *   Provides `get_tool_schema` to generate an OpenAI-compatible function/tool schema, which is crucial for LLMs to understand how to use the tool.
*   **Example Tools**:
    *   `MultiplyTool` (`src/tools/standard_tools.py`): Multiplies two integers.
    *   `RandomNumberTool` (`src/tools/example_tools.py`): Generates a random number in a given range.

### Chains

Chains define sequences or graphs of operations (involving tools and agents) to achieve a larger goal. They provide a way to structure complex workflows.

*   **`BaseChain` (`src/chains/base_chain.py`)**:
    *   Abstract base class for all chain implementations.
    *   Requires an `execute` method to be implemented by subclasses.
    *   Takes an `orchestrator` instance during initialization to access registered tools and agents.
*   **`ChainStep` (TypedDict in `src/chains/base_chain.py`)**:
    *   Defines the structure for a single step within a `SequentialStepChain`.
    *   Specifies the `type` ("tool" or "agent"), `key` (registration key), and optional `input_key`/`output_key` for managing data flow within a `workflow_context`.
*   **`SequentialStepChain` (`src/chains/base_chain.py`)**:
    *   A concrete chain that executes a list of `ChainStep`s in order.
    *   Manages a `workflow_context` dictionary to pass outputs from one step as inputs to the next, using `input_key` and `output_key` from `ChainStep`.
*   **`AgentAsChain` (`src/chains/base_chain.py`)**:
    *   A simple chain that wraps a single registered agent. Its `execute` method directly calls the agent's `run` method. This is useful for making an agent directly executable as a top-level workflow.

### Providers

Providers are clients or interfaces to external services, primarily Large Language Models.

*   **`GeminiClient` (`src/providers/gemini_client.py`)**:
    *   An implementation of `adalflow.core.model_client.ModelClient` for interacting with Google's Gemini models.
    *   Used by `BaseAgent` for making LLM calls as the default client
*   **`OllamaClient` (`src/providers/ollama_client.py`)**:
    *   An implementation of `adalflow.core.model_client.ModelClient` for interacting with Ollama hosted models locally.

### Memory

Memory components are responsible for storing and retrieving conversation history.

*   **`BaseMemory` (`src/memory/base_memory.py` - existence inferred)**:
    *   An abstract interface for memory services.
    *   Defines methods like `get_history` and `save_history`.
*   **`InMemoryMemoryService` (`src/memory/in_memory.py` - existence inferred)**:
    *   A concrete implementation of `BaseMemory` that stores conversation history in memory. Suitable for development and testing, but not for production persistence across application restarts.

### Observability

The toolkit integrates with OpenTelemetry for distributed tracing, providing insights into the execution flow of agents, tools, and LLM interactions.

*   **OpenTelemetry Setup**:
    *   Dependencies like `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, and `opentelemetry-instrumentation-fastapi` are included in `pyproject.toml`.
    *   Traces are likely configured to be exported to an OTLP-compatible backend. The inclusion of `arize-phoenix` and `arize-phoenix-otel` suggests Arize Phoenix might be the intended observability platform.
*   **`@trace_external_call` decorator (`src/observability/decorators.py`)**:
    *   A custom decorator to wrap functions (sync or async) and create OpenTelemetry spans for them.
    *   Captures function arguments, return values, and duration.
    *   Automatically includes `conversation_id` in the span attributes if available.
*   **Conversation ID (`CONV_ID_ATTRIBUTE`)**:
    *   A conversation ID is used to correlate traces belonging to the same interaction.
    *   The `conv_id_middleware.py` (inferred existence from `decorators.py`) likely sets this ID in OpenTelemetry Baggage at the API request boundary.
    *   `get_conversation_id()` and `set_conversation_id()` (`src/observability/context.py`) are used to propagate and access this ID.
*   **Detailed Tracing in Agents**:
    *   `BaseAgent` and `ToolAgent` create detailed child spans for:
        *   Overall agent execution (`agent_name.run`).
        *   Each iteration of the agent's reasoning loop (`agent_name.loop_iteration`).
        *   LLM calls (`agent_name.llm_response`), including attributes like model name and input.
        *   Tool argument parsing (`parse_tool_arguments.tool_name`).
        *   Tool execution (`tool_call.tool_name`), including arguments and output.
        *   Processing of tool calls (sequential or concurrent).
    *   OpenInference semantic conventions (e.g., `SpanAttributes.OPENINFERENCE_SPAN_KIND`) are used to categorize spans (LLM, AGENT, TOOL).

### Constants

*   **`registry_constants.py` (`src/orchestrators/registry_constants.py`)**:
    *   Defines string constants for keys used in the orchestrator's registries (e.g., `TOOL_MULTIPLY`, `AGENT_TOOL_ASSISTANT`, `CHAIN_TOOL_AGENT_WORKFLOW`).
    *   Promotes cleaner code by avoiding hardcoded strings and making it easier to manage and refactor identifiers.

## Project Structure

A brief overview of the key directories:

```
llm-toolkit/
├── src/
│   ├── agents/         # Agent implementations (BaseAgent, ToolAgent)
│   ├── api/            # FastAPI application, routers, middlewares
│   │   ├── middlewares/  # Request/response middlewares (e.g., conv_id_middleware)
│   │   └── routers/      # API endpoint definitions
│   ├── chains/         # Chain implementations (BaseChain, SequentialStepChain)
│   ├── config/         # Configuration files or constants
│   ├── memory/         # Conversation memory implementations
│   ├── observability/  # Tracing decorators, context management
│   ├── orchestrators/  # Orchestrator implementations, registry constants
│   ├── providers/      # LLM client implementations (e.g., GeminiClient)
│   ├── tools/          # Tool definitions (BaseTool, specific tools)
│   └── utils/          # Utility functions (logger, config loader)
├── tests/              # Unit and integration tests (recommended)
├── pyproject.toml      # Project metadata and dependencies
└── README.md           # This file
```

## Setup and Installation

### Prerequisites

*   Python 3.12.3 or higher
*   A virtual environment manager (e.g., `venv`, `conda`, `poetry`, `pdm`)

### Cloning the Repository

```bash
git clone <repository_url>
cd llm-toolkit
```

### Setting up Virtual Environment

Create a new virtual environment (optional, uv does this automatically if missing)

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Installing Dependencies

The project uses `pyproject.toml` for dependency management. You can install dependencies using `uv`:

```bash
uv pip install .
```

This command installs the package `llm-toolkit` and all its dependencies listed in `pyproject.toml`.

### Environment Variables

Copy the example environment file and edit it as needed

```bash
cp .env.template .env
```

## Running the Application

The toolkit includes a FastAPI application. To run it locally for development:

1.  **Ensure OpenTelemetry Collector (Optional but Recommended for Tracing)**:
    If you want to view traces locally or send them to a backend like Arize Phoenix, Jaeger, or Zipkin, ensure an OpenTelemetry Collector is running and configured to receive OTLP traces. The application will need to be configured with the collector's endpoint (e.g., via environment variables).

2.  **Start the FastAPI Server**:

    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

    *   `--reload`: Enables auto-reloading on code changes, useful for development.
    *   The server will typically be available at `http://localhost:8000`.

3.  **Access API Endpoints**:
    You can interact with the API using tools like `curl`, Postman, or by accessing the auto-generated OpenAPI documentation (usually at `http://localhost:8000/docs`).

    An example endpoint, based on previous interactions, might be:
    `POST /api/tasks/tool_agent`
    with a JSON body like:
    ```json
    {
        "user_message": "What is the capital of France and then multiply 5 by 7?"
    }
    ```
    You might also need to pass a `X-Conversation-ID` header if your middleware expects it for tracing.

## How to Extend

The modular design makes it easy to add new components:

### Adding New Tools

1.  Define your request and response Pydantic models.
2.  Create a new class that inherits from `BaseTool` (`src/tools/base_tool.py`).
3.  Implement the `name`, `description`, `request_model`, `response_model` attributes, and the `_handle` async method containing your tool's logic.
4.  Place the new tool file in `src/tools/`.
5.  Instantiate your new tool and register it with an orchestrator (e.g., in `ToolAgentWorkflowOrchestrator` or your custom orchestrator) using `orchestrator.register_tool(YOUR_TOOL_CONSTANT, your_tool_instance)`.
6.  Add a constant for your tool's key in `src/orchestrators/registry_constants.py`.
7.  Ensure your `ToolAgent` (or any agent that needs to use it) is configured with this new tool in its `tools` dictionary.

### Adding New Agents

1.  Create a new class that inherits from `BaseAgent` (`src/agents/base_agent.py`).
2.  Implement the `_agent_loop` method to define the agent's reasoning process.
3.  Customize constructor arguments as needed (e.g., different default prompt, LLM client).
4.  Place the new agent file in `src/agents/`.
5.  Instantiate your new agent and register it with an orchestrator using `orchestrator.register_agent(YOUR_AGENT_CONSTANT, your_agent_instance)`.
6.  Add a constant for your agent's key in `src/orchestrators/registry_constants.py`.

### Adding New Chains

1.  Create a new class that inherits from `BaseChain` (`src/chains/base_chain.py`).
2.  Implement the `execute` async method. This method will define how the chain processes input, interacts with registered tools/agents (via `self.orchestrator`), and produces an output.
3.  If creating a step-based chain, you might reuse or adapt the `ChainStep` model and logic from `SequentialStepChain`.
4.  Place the new chain file in `src/chains/`.
5.  Instantiate your new chain (passing the orchestrator instance to its constructor) and register it with an orchestrator using `orchestrator.register_chain(YOUR_CHAIN_CONSTANT, your_chain_instance)`.
6.  Add a constant for your chain's key in `src/orchestrators/registry_constants.py`.

## Contributing

Contributions are welcome! Please follow these general guidelines:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Write clean, well-documented code.
4.  Add unit tests for new functionality.
5.  Ensure all tests pass.
6.  Submit a pull request with a clear description of your changes.

---