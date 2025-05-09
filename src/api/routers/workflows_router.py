from fastapi import APIRouter
from pydantic import BaseModel

from api.models.workflows_models import ToolAgentRequest, ToolAgentResponse
from orchestrators.tool_agent_workflow_orchestrator import ToolAgentWorkflowOrchestrator

router = APIRouter(
    prefix="/api/workflows",
    tags=["workflows"],
)

@router.post("/tool_agent")
async def tool_agent(request: ToolAgentRequest):
    result = await ToolAgentWorkflowOrchestrator(user_message=request.message)
    return {"result": result}