from pydantic import BaseModel, Field
from typing import List, Optional

class FilePatch(BaseModel):
    path: str = Field(description="The path of the file to modify, relative to the repository root.")
    operation: str = Field(description="The operation to perform. Supported: 'modify', 'create'.")
    patch: str = Field(description="The unified diff for 'modify', or the full file content for 'create'.")

class RepairOutput(BaseModel):
    summary: str = Field(description="A concise 1-2 sentence summary of the repair candidate.")
    reasoning_summary: str = Field(description="A brief explanation of how the patch fixes the root cause.")
    expected_effect: str = Field(description="The expected behavior after applying this patch.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0 that this patch correctly resolves the bug without side effects.")
    files_changed: List[FilePatch] = Field(description="A list of proposed changes.")
