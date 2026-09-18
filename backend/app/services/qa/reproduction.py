import os
import shutil
import uuid
import logging
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt
from app.services.repository.clone import clone_repository, cleanup_workspace
from app.services.qa.llm_client import generate_reproduction_test
from app.services.testing.test_runner import run_tests_in_sandbox
from app.services.testing.command_resolver import resolve_test_command

logger = logging.getLogger(__name__)

def validate_test_path(repo_dir: str, test_file_path: str) -> str:
    """Ensure the path is safe and within the repository"""
    # Remove leading slashes
    clean_path = test_file_path.lstrip("/\\")
    full_path = os.path.abspath(os.path.join(repo_dir, clean_path))
    
    if not full_path.startswith(os.path.abspath(repo_dir)):
        raise ValueError(f"Invalid test path (path traversal detected): {test_file_path}")
        
    return full_path

def perform_reproduction(db: Session, analysis_id: str, attempt_id: str, bug_description: str) -> ReproductionAttempt:
    analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == analysis_id).first()
    if not analysis:
        raise ValueError("Analysis not found")
        
    attempt = db.query(ReproductionAttempt).filter(ReproductionAttempt.id == attempt_id).first()
    if not attempt:
        raise ValueError("Attempt not found")
    
    workspace_dir = None
    try:
        logger.info(f"reproduction_started analysis_id={analysis_id} reproduction_id={attempt_id} bug_description='{bug_description[:50]}...'")
        
        # 2. Gather context (simplistic for now, using relevant files from analysis)
        context_files = {}
        # We need a workspace to read files. Let's clone fresh to be safe.
        workspace_dir = clone_repository(analysis.repository_url)
        if not workspace_dir:
            raise Exception("Failed to prepare workspace")
            
        if analysis.relevant_files:
            for file_path in analysis.relevant_files:
                full_path = os.path.join(workspace_dir, file_path)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        # Limit content to avoid massive tokens
                        content = f.read()[:5000]
                        context_files[file_path] = content
                        
        # 3. Generate Test
        test_info = generate_reproduction_test(
            bug_description=bug_description,
            primary_language=analysis.primary_language,
            test_framework=analysis.test_framework or "pytest",
            context_files=context_files
        )
        logger.info(f"reproduction_test_generated analysis_id={analysis_id} reproduction_id={attempt_id} framework={test_info['test_framework']}")
        
        attempt.test_framework = test_info["test_framework"]
        attempt.test_code = test_info["test_code"]
        attempt.target_files = test_info["target_files"]
        attempt.hypothesis = test_info["hypothesis"]
        attempt.confidence = test_info["confidence"]
        db.commit()
        
        # 4. Inject test
        target_path = validate_test_path(workspace_dir, test_info["test_file_path"])
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Protect against overwriting existing files
        if os.path.exists(target_path):
            # Try to append a suffix
            target_path = target_path + "_repro_test.py"
            
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(test_info["test_code"])
            
        # 5. Run test
        # We need to run the specific test file.
        # We can use the command resolver to get the base command, then append the file path.
        base_cmd = resolve_test_command(workspace_dir, analysis.primary_language, test_info["test_framework"])
        
        # For simplicity, if it's pytest, we do `pytest <file>`. For npm test, it's harder to target one file safely generically.
        # So we might just run the specific test file if we know how, or run all tests (which is slower but safer).
        # Let's try to target if python
        if analysis.primary_language == "Python" and "pytest" in base_cmd:
            run_cmd = f"pytest {test_info['test_file_path']}"
        elif analysis.primary_language in ("JavaScript", "TypeScript") and "jest" in base_cmd:
            run_cmd = f"npx jest {test_info['test_file_path']}"
        else:
            # Fallback to base cmd
            run_cmd = base_cmd
            
        result = run_tests_in_sandbox(
            workspace_dir=workspace_dir,
            language=analysis.primary_language,
            test_command=run_cmd,
            framework=test_info["test_framework"]
        )
        
        # Log reproduction execution
        logger.info(
            f"reproduction_execution_completed analysis_id={analysis_id} reproduction_id={attempt_id} "
            f"command='{run_cmd}' exit_code={result.get('exit_code')} duration_ms={result.get('duration_ms')}"
        )
        
        # 6. Classify
        logger.info(f"reproduction_classification_started analysis_id={analysis_id} reproduction_id={attempt_id}")
        
        evidence = {
            "expected": test_info.get("expected_behavior", ""),
            "exit_code": result.get("exit_code"),
            "duration_ms": result.get("duration_ms"),
            "status": result.get("status"),
            "command": run_cmd,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", result.get("error_message", ""))
        }
        
        tests_total = result.get("tests_total", 0)
        exit_code = result.get("exit_code", 1)
        
        if result["status"] == "failed" and exit_code != 0 and tests_total > 0:
            # A failed test (with >0 tests parsed) means the bug is reproduced (the test asserts fixed behavior, but it failed).
            attempt.classification = "reproduced"
        elif result["status"] == "success" and exit_code == 0:
            # Test passed! Bug NOT reproduced.
            attempt.classification = "not_reproduced"
        else:
            # Either syntax error, timeout, install failure, or test framework crash (tests_total == 0)
            attempt.classification = "inconclusive"
            if tests_total == 0 and exit_code != 0:
                evidence["reason"] = "Test infrastructure failed or test collection crashed (0 tests parsed)."
            
        attempt.evidence = evidence
        db.commit()
        
        logger.info(f"reproduction_classification_completed analysis_id={analysis_id} reproduction_id={attempt_id} result={attempt.classification}")
        
    except Exception as e:
        logger.error(f"Reproduction failed: {e}")
        logger.info(f"reproduction_failed analysis_id={analysis_id} reproduction_id={attempt_id} error='{str(e)}'")
        attempt.classification = "inconclusive"
        attempt.evidence = {
            "status": "INCONCLUSIVE",
            "error_type": type(e).__name__,
            "reason": str(e),
            "command": getattr(e, "command", "N/A")
        }
        db.commit()
    finally:
        if workspace_dir:
            cleanup_workspace(workspace_dir)
            
    return attempt
