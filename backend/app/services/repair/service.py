import os
import json
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt, TestRun
from app.db.models.diagnosis import Diagnosis
from app.db.models.repair import Repair
from app.agents.repair.agent import RepairAgent
from app.services.repair.patch_validator import validate_patch
from app.services.repair.workspace import create_repair_workspace, apply_patch_to_workspace, cleanup_repair_workspace
from app.services.repair.diff import get_git_diff
from app.services.testing.test_runner import run_tests_in_sandbox

logger = logging.getLogger(__name__)

def generate_repair_candidate(db: Session, repair_id: str):
    """
    Background task to generate a repair candidate, validate it, apply it to a temporary workspace,
    and test it with the reproduction test.
    """
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        return

    workspace_path = None
    try:
        # Load context
        analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == repair.analysis_id).first()
        repro = db.query(ReproductionAttempt).filter(ReproductionAttempt.id == repair.reproduction_id).first()
        diagnosis = db.query(Diagnosis).filter(Diagnosis.id == repair.diagnosis_id).first()

        if not analysis or not repro or not diagnosis:
            raise ValueError("Missing required context records.")

        if repro.classification != "reproduced":
            raise ValueError("Repair requires a successfully reproduced defect.")

        if diagnosis.status not in ("completed", "validating"):
            raise ValueError("Repair requires a completed diagnosis.")

        repair.status = "generating"
        db.commit()

        # 1. Generate Patch
        agent = RepairAgent()
        
        # Pull code context from diagnosis
        code_contexts = [
            {"file": cc["file"], "content": cc["content"]} for cc in (diagnosis.code_context or [])
        ]
        
        repair_output = agent.generate_repair(
            bug_description=repro.bug_description,
            reproduction_evidence=diagnosis.evidence,
            diagnosis={
                "root_cause": diagnosis.root_cause,
                "failure_mechanism": diagnosis.failure_mechanism,
            },
            code_contexts=code_contexts
        )
        
        repair.summary = repair_output.summary
        repair.confidence = repair_output.confidence
        repair.status = "validating"
        db.commit()

        # 2. Validate Patch
        validate_patch(repair_output, [cc["file"] for cc in code_contexts])

        # 3. Create Workspace and Apply Patch
        repair.status = "applied"
        db.commit()
        
        workspace_path = create_repair_workspace(analysis.url)
        repair.workspace_id = os.path.basename(workspace_path)
        
        apply_patch_to_workspace(workspace_path, repair_output.files_changed)
        
        # 4. Get Actual Diff
        actual_diff = get_git_diff(workspace_path)
        repair.patch = actual_diff
        
        added = sum(1 for line in actual_diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in actual_diff.splitlines() if line.startswith("-") and not line.startswith("---"))
        
        repair.files_changed = len(repair_output.files_changed)
        repair.lines_added = added
        repair.lines_removed = removed
        db.commit()

        # 5. Run Targeted Test (Reproduction Test)
        repair.status = "tested"
        db.commit()
        
        # We need to run the reproduction test inside the workspace_path using the docker executor.
        test_file_path = "fixyron_reproduction_test.py" if repro.test_framework == "pytest" else "fixyron_reproduction.test.js"
        # Write test code to workspace
        full_test_path = os.path.join(workspace_path, test_file_path)
        with open(full_test_path, "w", encoding="utf-8") as f:
            f.write(repro.test_code)
            
        # Determine command based on framework. Simplify for now.
        if repro.test_framework == "pytest":
            command = f"pytest {test_file_path} -v"
        elif repro.test_framework == "jest":
            command = f"npx jest {test_file_path}"
        else:
            command = f"python {test_file_path}"

        result_dict = run_tests_in_sandbox(
            workspace_dir=workspace_path,
            language=analysis.primary_language,
            test_command=command,
            framework=repro.test_framework,
            timeout_seconds=60
        )
        
        repair.test_result = {
            "exit_code": result_dict.get("exit_code", 1),
            "stdout": result_dict.get("stdout", ""),
            "stderr": result_dict.get("stderr", result_dict.get("error_message", "")),
            "status": "passed" if result_dict.get("status") == "success" else "failed",
            "duration_ms": result_dict.get("duration_ms", 0)
        }
        
        if result_dict.get("status") == "success":
            repair.status = "completed"
        else:
            repair.status = "failed"
            repair.error_message = "Patch failed the reproduction test."

        db.commit()

    except Exception as e:
        logger.error(f"Repair task failed: {e}")
        repair.status = "error"
        repair.error_message = str(e)
        db.commit()
    finally:
        # Cleanup
        if workspace_path:
            cleanup_repair_workspace(workspace_path)
