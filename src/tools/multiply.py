from typing import Type

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.utils.logger import logger


# 1. Define Request Pydantic Model
class MultiplyRequest(BaseModel):
    a: int = Field(..., description="The first integer to multiply.")
    b: int = Field(..., description="The second integer to multiply.")

# 2. Define Response Pydantic Model
class MultiplyResponse(BaseModel):
    product: int = Field(..., description="The result of multiplying a and b.")

# 3. Create the Tool Class
class MultiplyTool(BaseTool[MultiplyRequest, MultiplyResponse]):
    name: str = "multiply"
    description: str = "Multiplies two integers and returns their product."
    request_model: Type[MultiplyRequest] = MultiplyRequest
    response_model: Type[MultiplyResponse] = MultiplyResponse

    async def _handle(self, request: MultiplyRequest) -> MultiplyResponse:
        logger.info(f"TOOL (MultiplyTool): Multiplying {request.a} by {request.b}")
        result = request.a * request.b
        return MultiplyResponse(product=result)
