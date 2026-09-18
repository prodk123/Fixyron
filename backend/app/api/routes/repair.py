from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from app.api.dependencies import get_db
from app.db.models.repair import Repair, RepairAttempt
from app.services.repair.service import generate_repair_candidate
from app.services.repair.workflow import run_repair_workflow

router = APIRouter()

class RepairRequest(BaseModel):
    analysis_id: str
    reproduction_id: str
    diagnosis_id: str

@router.post("/generate")
def generate_repair(request: RepairRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repair = Repair(
        analysis_id=request.analysis_id,
        reproduction_id=request.reproduction_id,
        diagnosis_id=request.diagnosis_id,
        status="pending"
    )
    db.add(repair)
    db.commit()
    db.refresh(repair)

    background_tasks.add_task(generate_repair_candidate, db, repair.id)

    return {"status": "success", "repair_id": repair.id}

@router.post("/{repair_id}/verify")
def verify_repair(repair_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
        
    if repair.final_status == "VERIFIED_FIXED":
        return {"status": "success", "message": "Repair is already verified", "repair_id": repair.id}
        
    # Start the LangGraph autonomous repair workflow
    background_tasks.add_task(run_repair_workflow, repair.id)
    
    return {"status": "success", "message": "Verification workflow started", "repair_id": repair.id}

@router.get("/{repair_id}")
def get_repair(repair_id: str, db: Session = Depends(get_db)):
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
        
    return {
        "id": repair.id,
        "analysis_id": repair.analysis_id,
        "reproduction_id": repair.reproduction_id,
        "diagnosis_id": repair.diagnosis_id,
        "status": repair.status,
        "summary": repair.summary,
        "confidence": repair.confidence,
        "files_changed": repair.files_changed,
        "lines_added": repair.lines_added,
        "lines_removed": repair.lines_removed,
        "patch": repair.patch,
        "patch_metadata": repair.patch_metadata,
        "test_result": repair.test_result,
        "error_message": repair.error_message,
        "created_at": repair.created_at,
        "completed_at": repair.completed_at,
        "max_attempts": repair.max_attempts,
        "current_attempt": repair.current_attempt,
        "final_status": repair.final_status,
        "verification_status": repair.verification_status
    }

@router.get("/{repair_id}/attempts")
def get_repair_attempts(repair_id: str, db: Session = Depends(get_db)):
    attempts = db.query(RepairAttempt).filter(RepairAttempt.repair_id == repair_id).order_by(RepairAttempt.attempt_number.asc()).all()
    return [{
        "id": a.id,
        "attempt_number": a.attempt_number,
        "strategy": a.strategy,
        "patch_metadata": a.patch_metadata,
        "validation_result": a.validation_result,
        "reproduction_result": a.reproduction_result,
        "regression_result": a.regression_result,
        "review": a.review,
        "failure_category": a.failure_category,
        "status": a.status,
        "error_message": a.error_message,
        "created_at": a.created_at,
        "completed_at": a.completed_at
    } for a in attempts]

@router.get("/analysis/{analysis_id}")
def get_repairs_for_analysis(analysis_id: str, db: Session = Depends(get_db)):
    repairs = db.query(Repair).filter(Repair.analysis_id == analysis_id).order_by(Repair.created_at.desc()).all()
    return [{
        "id": r.id,
        "analysis_id": r.analysis_id,
        "reproduction_id": r.reproduction_id,
        "diagnosis_id": r.diagnosis_id,
        "status": r.status,
        "summary": r.summary,
        "confidence": r.confidence,
        "files_changed": r.files_changed,
        "lines_added": r.lines_added,
        "lines_removed": r.lines_removed,
        "patch": r.patch,
        "patch_metadata": r.patch_metadata,
        "test_result": r.test_result,
        "error_message": r.error_message,
        "created_at": r.created_at,
        "completed_at": r.completed_at,
        "max_attempts": r.max_attempts,
        "current_attempt": r.current_attempt,
        "final_status": r.final_status,
        "verification_status": r.verification_status
    } for r in repairs]
