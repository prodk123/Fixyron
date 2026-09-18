from pydantic import BaseModel, Field
from typing import List

class PlannerOutput(BaseModel):
    strategy: str = Field(description="The new strategy for the Fix Agent to follow")
    reason: str = Field(description="Reasoning based on the reviewer feedback and test evidence")
    files_to_inspect: List[str] = Field(description="Files that the Fix Agent should look at")
    expected_change: str = Field(description="What the fix is expected to accomplish")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
