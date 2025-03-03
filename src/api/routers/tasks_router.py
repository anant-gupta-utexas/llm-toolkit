from fastapi import APIRouter

from src.orchestrators.api_orchestrator import ApiOrchestrator

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
)


@router.post("/test")
async def hello():
    result = ApiOrchestrator()
    return {"result": result}
