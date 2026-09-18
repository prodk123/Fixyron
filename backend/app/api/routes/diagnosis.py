"""
API routes for the Bug Diagnosis Agent.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api.dependencies import get_db
from app.schemas.diagnosis import DiagnosisRequest, DiagnosisResponse
from app.db.models.diagnosis import Diagnosis
from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt
from app.services.diagnosis.service import perform_diagnosis

router = APIRouter()


def start_diagnosis_background(diagnosis_id: str):
    """Background task for diagnosis execution."""
    from app.db.session import SessionLocal
    db: Session = SessionLocal()
    try:
        perform_diagnosis(db, diagnosis_id)
    finally:
        db.close()


@router.post("/analyze", response_model=DiagnosisResponse)
def trigger_diagnosis(
    request: DiagnosisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Start a bug diagnosis.
    Validates IDs, creates a pending Diagnosis record, and dispatches background work.
    """
    # Validate analysis exists
    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.id == request.analysis_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Validate reproduction exists
    reproduction = db.query(ReproductionAttempt).filter(
        ReproductionAttempt.id == request.reproduction_id
    ).first()
    if not reproduction:
        raise HTTPException(status_code=404, detail="Reproduction attempt not found")

    # Verify reproduction belongs to the analysis
    if reproduction.analysis_id != request.analysis_id:
        raise HTTPException(
            status_code=400,
            detail="Reproduction attempt does not belong to the specified analysis"
        )

    # Verify reproduction has evidence
    if not reproduction.evidence:
        raise HTTPException(
            status_code=400,
            detail="Reproduction attempt has no evidence. Run reproduction first."
        )

    # Create diagnosis record
    diagnosis = Diagnosis(
        analysis_id=request.analysis_id,
        reproduction_id=request.reproduction_id,
        status="pending",
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)

    # Dispatch background work
    background_tasks.add_task(start_diagnosis_background, diagnosis.id)

    return diagnosis


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
def get_diagnosis(diagnosis_id: str, db: Session = Depends(get_db)):
    """Retrieve a stored diagnosis by ID."""
    diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return diagnosis


@router.get("/analysis/{analysis_id}")
def get_diagnoses_for_analysis(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieve all diagnoses for an analysis."""
    diagnoses = db.query(Diagnosis).filter(
        Diagnosis.analysis_id == analysis_id
    ).order_by(Diagnosis.created_at.desc()).all()
    return diagnoses
