"""
Pydantic schemas for the diagnosis API request/response models.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class DiagnosisRequest(BaseModel):
    analysis_id: str
    reproduction_id: str


class EvidenceItemResponse(BaseModel):
    type: str
    file: Optional[str] = None
    line: Optional[int] = None
    description: str


class AlternativeCauseResponse(BaseModel):
    description: str
    confidence: float


class CodeContextResponse(BaseModel):
    file: str
    start_line: int
    end_line: int
    content: str
    score: float
    reason: str


class DiagnosisResponse(BaseModel):
    id: str
    analysis_id: str
    reproduction_id: str
    summary: Optional[str] = None
    root_cause: Optional[str] = None
    failure_mechanism: Optional[str] = None
    affected_files: Optional[List[str]] = None
    affected_functions: Optional[List[str]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    alternative_causes: Optional[List[Dict[str, Any]]] = None
    code_context: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    status: str
    model: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
