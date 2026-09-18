from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api.dependencies import get_db
from app.schemas.repository import RepositoryAnalysisRequest, RepositoryAnalysisResponse
from app.db.models.repository import RepositoryAnalysis
from app.services.repository.validation import validate_github_url
import uuid

from app.services.analysis.analyzer import perform_analysis

router = APIRouter()

def start_analysis_background(analysis_id: str, request: RepositoryAnalysisRequest):
    perform_analysis(analysis_id, request)

@router.post("/analyze", response_model=RepositoryAnalysisResponse)
def analyze_repository(
    request: RepositoryAnalysisRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Validate URL before proceeding
    validate_github_url(request.repository_url)

    analysis_id = str(uuid.uuid4())
    
    # Store initial record
    db_analysis = RepositoryAnalysis(
        id=analysis_id,
        repository_url=str(request.repository_url),
        bug_description=request.bug_description,
        status="pending"
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    
    # Start analysis in background
    background_tasks.add_task(start_analysis_background, analysis_id, request)
    
    # Returning a basic response according to schema
    # (Since background task isn't modifying it immediately, we construct from db model)
    return RepositoryAnalysisResponse(
        analysis_id=db_analysis.id,
        repository={
            "url": db_analysis.repository_url,
            "name": db_analysis.repository_name,
            "primary_language": db_analysis.primary_language,
            "framework": db_analysis.framework,
            "file_count": db_analysis.file_count,
            "estimated_loc": db_analysis.estimated_loc,
            "has_readme": db_analysis.has_readme,
        },
        testing={
            "framework": db_analysis.test_framework,
            "test_file_count": db_analysis.test_file_count,
        },
        structure={
            "important_directories": db_analysis.important_directories or []
        },
        relevant_files=db_analysis.relevant_files or [],
        status=db_analysis.status,
        error_message=db_analysis.error_message,
        created_at=db_analysis.created_at,
        completed_at=db_analysis.completed_at
    )

@router.get("/{analysis_id}", response_model=RepositoryAnalysisResponse)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    db_analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == analysis_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    return RepositoryAnalysisResponse(
        analysis_id=db_analysis.id,
        repository={
            "url": db_analysis.repository_url,
            "name": db_analysis.repository_name,
            "primary_language": db_analysis.primary_language,
            "framework": db_analysis.framework,
            "file_count": db_analysis.file_count,
            "estimated_loc": db_analysis.estimated_loc,
            "has_readme": db_analysis.has_readme,
        },
        testing={
            "framework": db_analysis.test_framework,
            "test_file_count": db_analysis.test_file_count,
        },
        structure={
            "important_directories": db_analysis.important_directories or []
        },
        relevant_files=db_analysis.relevant_files or [],
        status=db_analysis.status,
        error_message=db_analysis.error_message,
        created_at=db_analysis.created_at,
        completed_at=db_analysis.completed_at
    )
