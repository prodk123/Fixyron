"""
Pydantic schemas for the diagnosis agent's structured LLM output.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting the diagnosis."""
    type: str = Field(
        description="Type of evidence: stack_trace, test_failure, source_location, reproduction_result, exception, configuration"
    )
    file: Optional[str] = Field(
        default=None,
        description="File path related to this evidence"
    )
    line: Optional[int] = Field(
        default=None,
        description="Line number if applicable"
    )
    description: str = Field(
        description="Description of what this evidence shows"
    )


class AlternativeCause(BaseModel):
    """A possible alternative root cause."""
    description: str = Field(
        description="Description of the alternative cause"
    )
    confidence: float = Field(
        description="Confidence score for this alternative (0.0 to 1.0)"
    )


class DiagnosisOutput(BaseModel):
    """Complete structured diagnosis from the LLM."""
    summary: str = Field(
        description="One-sentence summary of the diagnosis"
    )
    root_cause: str = Field(
        description="Detailed explanation of the root cause, distinguishing it from symptoms"
    )
    affected_files: List[str] = Field(
        default_factory=list,
        description="List of file paths that contain the defect"
    )
    affected_functions: List[str] = Field(
        default_factory=list,
        description="List of function/method names that are responsible"
    )
    failure_mechanism: str = Field(
        description="Technical explanation of how the failure occurs"
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list,
        description="Concrete evidence supporting this diagnosis"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0"
    )
    alternative_causes: List[AlternativeCause] = Field(
        default_factory=list,
        description="Possible alternative root causes, if any"
    )
