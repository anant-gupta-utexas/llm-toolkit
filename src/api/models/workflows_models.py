from uuid import uuid4

from pydantic import BaseModel, Field


class ToolAgentRequest(BaseModel):
    """
    Request model for ToolAgent.
    """
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    message: str
    model: str = "GEMINI_2.0_FLASH"

class ToolAgentResponse(BaseModel):
    """
    Response model for ToolAgent.
    """
    conversation_id: str
    # TODO: Check and update this based on message response model from LLM provider
    intermediate_steps: list
    final_response: str
    error: bool = False
    error_message: str = None