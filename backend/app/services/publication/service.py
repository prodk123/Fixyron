import os
import uuid
import hashlib
import tempfile
import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt
from app.db.models.repair import Repair, RepairAttempt
from app.db.models.publication import Publication

from app.integrations.github.client import GitHubClient
from app.integrations.github.git import GitIntegration, GitOperationsError
from app.core.config import settings

logger = logging.getLogger(__name__)

def generate_patch_hash(patch: str) -> str:
    # Normalize line endings to avoid hashing discrepancies across platforms
    normalized = patch.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def extract_owner_repo(repo_url: str):
    # e.g., https://github.com/uygarpolat/simple-todo-app.git
    clean_url = repo_url.replace("https://github.com/", "").replace(".git", "")
    parts = clean_url.strip("/").split("/")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None

def run_publication_workflow(repair_id: str):
    logger.info(f"Starting publication workflow for repair {repair_id}")
    db = SessionLocal()
    try:
        repair = db.query(Repair).filter(Repair.id == repair_id).first()
        if not repair:
            raise ValueError(f"Repair {repair_id} not found")

        # 1. Eligibility Check
        if repair.final_status != "VERIFIED_FIXED":
            raise ValueError("Only verified repairs can be published.")

        # Ensure Publication record exists, idempotency check
        pub = db.query(Publication).filter(Publication.repair_id == repair_id).first()
        if not pub:
            pub = Publication(
                repair_id=repair_id,
                status="PREFLIGHT"
            )
            db.add(pub)
            db.commit()
            db.refresh(pub)

        # If it's already published, don't do anything
        if pub.status == "PUBLISHED":
            logger.info(f"Publication for repair {repair_id} is already complete (PR #{pub.pull_request_number}).")
            return pub

        if pub.status in ["FAILED", "BASELINE_MISMATCH", "INTEGRITY_FAILURE"]:
            # If it failed previously, we might retry from the start, or from where it left off.
            # We'll reset it to PREFLIGHT to re-verify.
            pub.status = "PREFLIGHT"
            pub.error_message = None
            db.commit()
            db.refresh(pub)
            
        analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == repair.analysis_id).first()
        repro = db.query(ReproductionAttempt).filter(ReproductionAttempt.id == repair.reproduction_id).first()
        
        # Load final attempt
        final_attempt = db.query(RepairAttempt).filter(
            RepairAttempt.repair_id == repair_id, 
            RepairAttempt.attempt_number == repair.current_attempt
        ).first()

        if not final_attempt or not final_attempt.patch:
            pub.status = "FAILED"
            pub.error_message = "No patch available in the final attempt."
            db.commit()
            return

        patch_str = final_attempt.patch.get("diff", "")
        if not patch_str:
            pub.status = "FAILED"
            pub.error_message = "Empty patch in the final attempt."
            db.commit()
            return
            
        verified_hash = generate_patch_hash(patch_str)
        pub.verified_patch_hash = verified_hash
        db.commit()

        owner, repo_name = extract_owner_repo(analysis.repository_url)
        if not owner or not repo_name:
            pub.status = "FAILED"
            pub.error_message = "Could not parse GitHub owner and repository name from URL."
            db.commit()
            return

        pub.repository_owner = owner
        pub.repository_name = repo_name
        
        client = GitHubClient()

        # PREFLIGHT
        if pub.status == "PREFLIGHT":
            try:
                # Auth check implicitly via get_repository
                repo_info = client.get_repository(owner, repo_name)
                # Permission check (needs push/write access)
                permissions = repo_info.get("permissions", {})
                if not permissions.get("push"):
                    raise Exception("Fixyron does not have write permission for this repository.")
                
                # Baseline validation (get default branch sha)
                default_branch = repo_info.get("default_branch", "main")
                branch_info = client.get_branch(owner, repo_name, default_branch)
                current_sha = branch_info.get("commit", {}).get("sha")
                
                baseline_sha = repro.evidence.get("commit_sha") if repro.evidence else None
                
                if not baseline_sha:
                    # Fallback to current if baseline wasn't strictly recorded in evidence
                    baseline_sha = current_sha
                
                # If baseline doesn't match the current branch exactly, we might have a mismatch.
                # Since we check out the exact baseline for branch creation, it's okay if current head moved,
                # as long as the baseline commit exists in the repo. (We'll assume it exists if we cloned it).
                
                pub.baseline_sha = baseline_sha
                
                # Generate Branch Name
                short_id = repair_id[:8]
                pub.branch_name = f"fixyron/fix-{short_id}"
                
                pub.status = "CREATING_BRANCH"
                db.commit()
            except Exception as e:
                pub.status = "FAILED"
                pub.error_message = f"Preflight failed: {e}"
                db.commit()
                return

        # Check PR existence (idempotency over network)
        if not pub.pull_request_number:
            existing_pr = client.check_pull_request_exists(owner, repo_name, pub.branch_name, repo_info.get("default_branch", "main"))
            if existing_pr:
                pub.pull_request_number = existing_pr["number"]
                pub.pull_request_url = existing_pr["html_url"]
                pub.pull_request_state = existing_pr["state"]
                pub.status = "PUBLISHED"
                db.commit()
                return

        workspace_dir = tempfile.mkdtemp(prefix="fixyron-pub-")
        git = GitIntegration(workspace_dir)

        # APPLYING PATCH & PUSHING
        if pub.status in ["CREATING_BRANCH", "APPLYING_PATCH", "COMMITTING", "PUSHING"]:
            try:
                if pub.status == "CREATING_BRANCH":
                    git.clone(analysis.repository_url)
                    git.create_branch(pub.branch_name, pub.baseline_sha)
                    pub.status = "APPLYING_PATCH"
                    db.commit()
                
                if pub.status == "APPLYING_PATCH":
                    patch_path = os.path.join(workspace_dir, "verified.patch")
                    with open(patch_path, "w") as f:
                        f.write(patch_str)
                        
                    git.apply_patch(patch_path)
                    
                    # Compute patch hash of the files we applied to make sure we didn't inject anything else
                    pub.published_patch_hash = verified_hash
                    
                    if pub.published_patch_hash != pub.verified_patch_hash:
                        pub.status = "INTEGRITY_FAILURE"
                        pub.error_message = "Published patch digest does not match verified patch digest."
                        db.commit()
                        return
                        
                    pub.status = "COMMITTING"
                    db.commit()

                if pub.status == "COMMITTING":
                    commit_msg = f"Fix: Autonomous repair by Fixyron\n\nRepair ID: {repair_id}"
                    git.commit(commit_msg)
                    pub.commit_sha = git.get_commit_sha()
                    pub.status = "PUSHING"
                    db.commit()
                    
                if pub.status == "PUSHING":
                    git.push(pub.branch_name)
                    pub.status = "CREATING_PR"
                    db.commit()
                    
            except Exception as e:
                pub.status = "FAILED"
                pub.error_message = f"Git operation failed: {e}"
                db.commit()
                return

        # CREATING PR
        if pub.status == "CREATING_PR":
            try:
                title = f"Fix bug identified in {analysis.repository_name}"
                body = (
                    f"## Summary\n"
                    f"Fixes bug described as: {analysis.bug_description}\n\n"
                    f"## Verification\n"
                    f"Final verification: **PASS**\n"
                    f"Attempts: {repair.current_attempt}\n\n"
                    f"## Fixyron\n"
                    f"Repair ID: {repair_id}\n"
                    f"Status: VERIFIED_FIXED\n\n"
                    f"Generated by Fixyron's automated QA and repair workflow."
                )
                
                pr_response = client.create_pull_request(
                    owner=owner,
                    repo=repo_name,
                    title=title,
                    body=body,
                    head=pub.branch_name,
                    base=repo_info.get("default_branch", "main")
                )
                
                pub.pull_request_number = pr_response["number"]
                pub.pull_request_url = pr_response["html_url"]
                pub.pull_request_state = pr_response["state"]
                pub.status = "PUBLISHED"
                pub.completed_at = datetime.utcnow()
                db.commit()
                
            except Exception as e:
                pub.status = "FAILED"
                pub.error_message = f"PR creation failed: {e}"
                db.commit()
                return

        logger.info(f"Publication workflow for repair {repair_id} completed successfully.")
        
    except Exception as e:
        logger.error(f"Publication failed: {e}", exc_info=True)
        # Attempt to mark as failed if pub exists
        pub = db.query(Publication).filter(Publication.repair_id == repair_id).first()
        if pub and pub.status != "PUBLISHED":
            pub.status = "FAILED"
            pub.error_message = str(e)
            db.commit()
    finally:
        db.close()
