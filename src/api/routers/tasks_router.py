from fastapi import APIRouter
from pydantic import BaseModel

from src.api.models.tasks_models import ToolAgentRequest, ToolAgentResponse
from src.orchestrators.api_orchestrator import ApiOrchestrator
from src.orchestrators.tool_agent_orchestrator import ToolAgentOrchestrator

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
)

@router.post("/test")
async def test(request: None):
    result = await ApiOrchestrator()
    return {"result": result}


@router.post("/tool_agent")
async def tool_agent(request: ToolAgentRequest):
    # Pass the user message from the request body to the orchestrator
    result = await ToolAgentOrchestrator(user_message=request.message)
    return {"result": result}