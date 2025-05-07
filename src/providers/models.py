from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ContentRole(str, Enum):
    USER = "user"
    MODEL = "model"
    TOOL = "tool"


class PartType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESPONSE = "function_response"


class Schema(BaseModel):
    type: str
    properties: Dict[str, Any] = {}
    required: List[str] = []


class FunctionDeclaration(BaseModel):
    name: str
    description: str
    parameters: Schema


class FunctionCall(BaseModel):
    name: str
    args: Dict[str, Any]


class FunctionResponse(BaseModel):
    name: str
    response: Dict[str, Any]


class TextPart(BaseModel):
    text: str
    type: Literal[PartType.TEXT] = PartType.TEXT


class ImagePart(BaseModel):
    uri: str
    mime_type: str
    type: Literal[PartType.IMAGE] = PartType.IMAGE


class FunctionCallPart(BaseModel):
    function_call: FunctionCall
    type: Literal[PartType.FUNCTION_CALL] = PartType.FUNCTION_CALL


class FunctionResponsePart(BaseModel):
    function_response: FunctionResponse
    type: Literal[PartType.FUNCTION_RESPONSE] = PartType.FUNCTION_RESPONSE


class Content(BaseModel):
    role: ContentRole
    parts: List[Union[TextPart, ImagePart, FunctionCallPart, FunctionResponsePart]]


class Tool(BaseModel):
    function_declarations: List[FunctionDeclaration]


class GenerateContentConfig(BaseModel):
    tools: List[Union[Tool, Any]] = Field(default_factory=list)
    response_mime_type: Optional[str] = None
    response_schema: Optional[Union[Dict[str, Any], Any]] = None
    tool_config: Optional[Dict[str, Any]] = None
    automatic_function_calling: Optional[Dict[str, Any]] = None


class MessageInput(BaseModel):
    """Input for building messages that can be passed to the function."""

    text: Optional[str] = None
    image_uri: Optional[str] = None
    image_mime_type: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    function_response: Optional[FunctionResponse] = None
    role: ContentRole = ContentRole.USER
