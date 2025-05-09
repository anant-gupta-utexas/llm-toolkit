import random
from typing import Type

from pydantic import BaseModel, Field

from src.tools.base_tool import BaseTool
from src.utils.logger import logger


class RandomNumberRequest(BaseModel):
    min_val: int = Field(
        ..., description="The minimum value for the random number (inclusive)."
    )
    max_val: int = Field(
        ..., description="The maximum value for the random number (inclusive)."
    )


class RandomNumberResponse(BaseModel):
    random_number: int = Field(..., description="The generated random integer.")


class GenerateRandomNumberTool(BaseTool[RandomNumberRequest, RandomNumberResponse]):
    name: str = "generate_random_number"
    description: str = "Generates a random integer between a specified minimum and maximum (inclusive)."
    request_model: Type[RandomNumberRequest] = RandomNumberRequest
    response_model: Type[RandomNumberResponse] = RandomNumberResponse

    async def _handle(self, request: RandomNumberRequest) -> RandomNumberResponse:
        if request.min_val > request.max_val:
            logger.warning(
                f"TOOL ({self.name}): min_val ({request.min_val}) is greater than max_val ({request.max_val}). Swapping them."
            )
            request.min_val, request.max_val = request.max_val, request.min_val

        logger.info(
            f"TOOL ({self.name}): Generating random number between {request.min_val} and {request.max_val}"
        )
        generated_number = random.randint(request.min_val, request.max_val)
        return RandomNumberResponse(random_number=generated_number)
