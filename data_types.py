"""All Pydantic models for finetuner.dev. No logic, no I/O."""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict


class ToolResult(BaseModel):
    tool_name: str
    result: str
    is_error: bool


class Candidate(BaseModel):
    response: str
    score: float = 0.0
    score_reason: str = ""
    accepted: bool = False


class Sample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["single", "multi"]
    user_turn: str
    candidates: list[Candidate] = Field(default_factory=list)
    accepted_response: str = ""
    topic: str = ""
    persona: str = ""


class TokenUsage(BaseModel):
    role: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class ValidatorOutput(BaseModel):
    accepted: bool
    reason: str


class ScoreOutput(BaseModel):
    score: float
    reason: str


class CheckpointState(BaseModel):
    phase_1_complete: bool = False
    phase_2_complete: bool = False
    phase_3_complete: bool = False
    phase_4_complete: bool = False
    phase_5_complete: bool = False
    single_completed: int = 0
    multi_completed: int = 0
