from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.repair import Repair
from app.db.models.publication import Publication
from app.services.publication.service import run_publication_workflow

router = APIRouter()

@router.post("/{repair_id}/publish")
def trigger_publication(repair_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    if repair.final_status != "VERIFIED_FIXED":
        raise HTTPException(status_code=400, detail="Only VERIFIED_FIXED repairs can be published")

    pub = db.query(Publication).filter(Publication.repair_id == repair_id).first()
    if pub and pub.status == "PUBLISHED":
        return {"message": "Already published", "publication_id": pub.id}
        
    background_tasks.add_task(run_publication_workflow, repair_id)
    return {"message": "Publication workflow started"}

@router.get("/{repair_id}/publication")
def get_publication(repair_id: str, db: Session = Depends(get_db)):
    pub = db.query(Publication).filter(Publication.repair_id == repair_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication record not found")
        
    return {
        "id": pub.id,
        "repair_id": pub.repair_id,
        "status": pub.status,
        "pull_request_url": pub.pull_request_url,
        "pull_request_number": pub.pull_request_number,
        "pull_request_state": pub.pull_request_state,
        "branch_name": pub.branch_name,
        "commit_sha": pub.commit_sha,
        "error_message": pub.error_message,
        "created_at": pub.created_at,
        "completed_at": pub.completed_at
    }
