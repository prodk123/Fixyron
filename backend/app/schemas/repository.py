from pydantic import BaseModel, HttpUrl, AnyUrl
from typing import Optional, List, Dict, Any
from datetime import datetime

class RepositoryAnalysisRequest(BaseModel):
    repository_url: AnyUrl
    bug_description: Optional[str] = None

class RepositoryInfo(BaseModel):
    url: str
    name: Optional[str] = None
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    file_count: int = 0
    estimated_loc: int = 0
    has_readme: bool = False

class TestingInfo(BaseModel):
    framework: Optional[str] = None
    test_file_count: int = 0

class RepositoryStructure(BaseModel):
    important_directories: List[str] = []

class RepositoryAnalysisResponse(BaseModel):
    analysis_id: str
    repository: RepositoryInfo
    testing: TestingInfo
    structure: RepositoryStructure
    relevant_files: List[str] = []
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
