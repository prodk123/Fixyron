from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api.dependencies import get_db
from app.schemas.qa import BugReproductionRequest, ReproductionAttemptResponse, RunTestsRequest, TestRunResponse
from app.db.models.qa import ReproductionAttempt, TestRun
from app.db.models.repository import RepositoryAnalysis
from app.services.qa.reproduction import perform_reproduction
from app.services.testing.test_runner import run_tests_in_sandbox
from app.services.testing.command_resolver import resolve_test_command
from app.services.repository.clone import clone_repository, cleanup_workspace
import uuid

router = APIRouter()

def start_reproduction_background(analysis_id: str, attempt_id: str, bug_description: str):
    db: Session = next(get_db())
    try:
        perform_reproduction(db, analysis_id, attempt_id, bug_description)
    finally:
        db.close()

@router.post("/reproduction", response_model=ReproductionAttemptResponse)
def trigger_reproduction(
    request: BugReproductionRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == request.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    # We return a pending state and do the work in the background, or do it synchronously if we want to block.
    # The instructions say: "Start reproduction in the background". Let's do background for the actual test.
    # But wait! To give immediate feedback, let's create the record synchronously.
    
    attempt = ReproductionAttempt(
        analysis_id=request.analysis_id,
        bug_description=request.bug_description,
        classification="pending"
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    background_tasks.add_task(start_reproduction_background, request.analysis_id, attempt.id, request.bug_description)
    
    return attempt

@router.get("/reproduction/{reproduction_id}", response_model=ReproductionAttemptResponse)
def get_reproduction(reproduction_id: str, db: Session = Depends(get_db)):
    attempt = db.query(ReproductionAttempt).filter(ReproductionAttempt.id == reproduction_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Reproduction attempt not found")
    return attempt

@router.get("/reproduction/analysis/{analysis_id}")
def get_reproductions_for_analysis(analysis_id: str, db: Session = Depends(get_db)):
    attempts = db.query(ReproductionAttempt).filter(ReproductionAttempt.analysis_id == analysis_id).order_by(ReproductionAttempt.created_at.desc()).all()
    return attempts

def run_existing_tests_background(analysis_id: str):
    db: Session = next(get_db())
    workspace_dir = None
    try:
        analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == analysis_id).first()
        if not analysis:
            return
            
        test_run = TestRun(
            analysis_id=analysis_id,
            status="running"
        )
        db.add(test_run)
        db.commit()
        db.refresh(test_run)
        
        workspace_dir = clone_repository(analysis.repository_url)
        if not workspace_dir:
            test_run.status = "error"
            db.commit()
            return
            
        cmd = resolve_test_command(workspace_dir, analysis.primary_language, analysis.test_framework)
        test_run.command = cmd
        test_run.framework = analysis.test_framework
        db.commit()
        
        result = run_tests_in_sandbox(
            workspace_dir=workspace_dir,
            language=analysis.primary_language,
            test_command=cmd,
            framework=analysis.test_framework
        )
        
        test_run.status = result["status"]
        test_run.exit_code = result.get("exit_code")
        test_run.tests_total = result.get("tests_total", 0)
        test_run.tests_passed = result.get("tests_passed", 0)
        test_run.tests_failed = result.get("tests_failed", 0)
        test_run.tests_skipped = result.get("tests_skipped", 0)
        test_run.stdout = result.get("stdout")
        test_run.stderr = result.get("stderr")
        test_run.duration_ms = result.get("duration_ms")
        test_run.timed_out = result.get("timed_out", False)
        
        db.commit()
        
    finally:
        if workspace_dir:
            cleanup_workspace(workspace_dir)
        db.close()

@router.post("/tests/run")
def trigger_existing_tests(request: RunTestsRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == request.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    background_tasks.add_task(run_existing_tests_background, request.analysis_id)
    return {"status": "started"}

@router.get("/tests/analysis/{analysis_id}")
def get_test_runs_for_analysis(analysis_id: str, db: Session = Depends(get_db)):
    runs = db.query(TestRun).filter(TestRun.analysis_id == analysis_id).order_by(TestRun.created_at.desc()).all()
    # We can omit stdout for the list view
    return [
        {
            "id": run.id,
            "status": run.status,
            "framework": run.framework,
            "command": run.command,
            "tests_total": run.tests_total,
            "tests_passed": run.tests_passed,
            "tests_failed": run.tests_failed,
            "created_at": run.created_at,
            "duration_ms": run.duration_ms
        }
        for run in runs
    ]

@router.get("/tests/{run_id}")
def get_test_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(TestRun).filter(TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run
