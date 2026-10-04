from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TriageRequest(BaseModel):
    description: str = Field(..., min_length=5, description="What the engineer is seeing")
    device_name: str | None = Field(None, description="Affected device, if known")
    create_ticket: bool = Field(False, description="Allow the assistant to open a fault ticket")


class TriageResult(BaseModel):
    mode: Literal["llm", "offline"]
    likely_category: str
    suggested_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    likely_root_cause: str
    recommended_steps: list[str]
    confidence: float = Field(..., ge=0, le=1)
    cited_fault_ids: list[int]
    similar_faults: list[dict] = []
    actions_taken: list[dict] = []
    summary: str = ""
