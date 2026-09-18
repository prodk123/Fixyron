from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class BugReproductionRequest(BaseModel):
    analysis_id: str
    bug_description: str

class ReproductionAttemptResponse(BaseModel):
    id: str
    analysis_id: str
    bug_description: str
    test_framework: Optional[str] = None
    test_code: Optional[str] = None
    target_files: Optional[List[str]] = None
    hypothesis: Optional[str] = None
    classification: str
    evidence: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    created_at: datetime

class RunTestsRequest(BaseModel):
    analysis_id: str

class TestRunResponse(BaseModel):
    id: str
    analysis_id: str
    framework: Optional[str] = None
    command: Optional[str] = None
    status: str
    exit_code: Optional[int] = None
    tests_total: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    duration_ms: Optional[int] = None
    timed_out: bool
    created_at: datetime
    # Omitting stdout/stderr to avoid huge responses, unless specifically requested
