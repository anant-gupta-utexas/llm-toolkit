from fastapi import APIRouter
from pydantic import BaseModel

from api.models.workflows import ToolAgentRequest, ToolAgentResponse
from src.orchestrators.api_orchestrator import ApiOrchestrator
from src.orchestrators.tool_agent_workflow import ToolAgentWorkflowOrchestrator

router = APIRouter(
    prefix="/api/workflows",
    tags=["workflows"],
)

@router.post("/tool_agent")
async def tool_agent(request: ToolAgentRequest):
    # Pass the user message from the request body to the orchestrator
    result = await ToolAgentWorkflowOrchestrator(user_message=request.message)
    return {"result": result}