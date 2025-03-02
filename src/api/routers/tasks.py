from fastapi import APIRouter

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
)


@router.get("/hello")
async def hello():
    return {"message": "Hello from tasks router"}
