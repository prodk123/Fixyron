import os
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt, TestRun
from app.db.models.diagnosis import Diagnosis
from app.db.models.repair import Repair, RepairAttempt
from app.agents.repair.agent import RepairAgent
from app.services.repair.patch_validator import validate_patch
from app.services.repair.workspace import create_repair_workspace, apply_patch_to_workspace, cleanup_repair_workspace
from app.services.repair.diff import get_git_diff
from app.services.testing.test_runner import run_tests_in_sandbox
from app.agents.reviewer.agent import ReviewerAgent
from app.agents.planner.agent import PlannerAgent
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

class RepairState(dict):
    repair_id: str
    db_session: Session
    
    # Context
    analysis: Any
    reproduction: Any
    diagnosis: Any
    code_contexts: List[Dict[str, Any]]
    
    # State tracking
    current_attempt_num: int
    max_attempts: int
    
    # Current attempt variables
    attempt_id: str
    planner_strategy: Optional[Dict[str, Any]]
    patch: Optional[Dict[str, Any]]
    workspace_path: Optional[str]
    reproduction_result: Optional[Dict[str, Any]]
    regression_result: Optional[Dict[str, Any]]
    reviewer_output: Optional[Dict[str, Any]]
    
    # Final states
    final_status: str
    error_message: Optional[str]


def _persist_attempt_state(state: RepairState, attempt_status: str):
    db = state['db_session']
    attempt = db.query(RepairAttempt).filter(RepairAttempt.id == state['attempt_id']).first()
    if attempt:
        attempt.status = attempt_status
        if state['planner_strategy']:
            attempt.strategy = state['planner_strategy']
        if state['patch']:
            attempt.patch = state['patch']
        if state['workspace_path']:
            attempt.workspace_id = os.path.basename(state['workspace_path'])
        if state['reproduction_result']:
            attempt.reproduction_result = state['reproduction_result']
        if state['regression_result']:
            attempt.regression_result = state['regression_result']
        if state['reviewer_output']:
            attempt.review = state['reviewer_output']
            attempt.failure_category = state['reviewer_output'].get('failure_category')
        db.commit()


def node_load_repair_context(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] load_repair_context for repair {state['repair_id']}")
    db = state['db_session']
    repair = db.query(Repair).filter(Repair.id == state['repair_id']).first()
    
    analysis = db.query(RepositoryAnalysis).filter(RepositoryAnalysis.id == repair.analysis_id).first()
    repro = db.query(ReproductionAttempt).filter(ReproductionAttempt.id == repair.reproduction_id).first()
    diagnosis = db.query(Diagnosis).filter(Diagnosis.id == repair.diagnosis_id).first()
    
    state['analysis'] = analysis
    state['reproduction'] = repro
    state['diagnosis'] = diagnosis
    state['code_contexts'] = [
        {"file": cc["file"], "content": cc["content"]} for cc in (diagnosis.code_context or [])
    ]
    
    state['max_attempts'] = repair.max_attempts
    state['current_attempt_num'] = repair.current_attempt + 1
    
    if state['current_attempt_num'] > state['max_attempts']:
        state['final_status'] = "REPAIR_FAILED"
        state['error_message'] = "Maximum attempts reached before starting."
        return state
        
    repair.current_attempt = state['current_attempt_num']
    repair.status = "generating"
    
    # Create attempt record
    attempt = RepairAttempt(
        repair_id=repair.id,
        attempt_number=state['current_attempt_num'],
        status="generating",
        strategy=state['planner_strategy']
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    state['attempt_id'] = attempt.id
    return state


def node_generate_patch(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] generate_patch - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    db = state['db_session']
    
    # Fetch previous attempts to provide context
    previous_attempts_records = db.query(RepairAttempt).filter(
        RepairAttempt.repair_id == state['repair_id'],
        RepairAttempt.attempt_number < state['current_attempt_num']
    ).order_by(RepairAttempt.attempt_number.asc()).all()
    
    previous_attempts = [
        {
            "attempt": a.attempt_number,
            "strategy": a.strategy,
            "patch": a.patch,
            "review": a.review
        } for a in previous_attempts_records
    ]

    agent = RepairAgent()
    repair_output = agent.generate_repair(
        bug_description=state['reproduction'].bug_description,
        reproduction_evidence=state['diagnosis'].evidence,
        diagnosis={
            "root_cause": state['diagnosis'].root_cause,
            "failure_mechanism": state['diagnosis'].failure_mechanism,
        },
        code_contexts=state['code_contexts'],
        planner_strategy=state['planner_strategy'],
        previous_attempts=previous_attempts
    )
    
    state['patch'] = repair_output.model_dump()
    _persist_attempt_state(state, "patch_generated")
    
    return state

def node_validate_patch(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] validate_patch - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    try:
        # Pydantic validates during coercion, but we also enforce security limits
        repair_output = state['patch']
        # The validate_patch function expects a RepairOutput instance
        from app.agents.repair.schemas import RepairOutput
        ro = RepairOutput.model_validate(repair_output)
        validate_patch(ro, [cc["file"] for cc in state['code_contexts']])
        _persist_attempt_state(state, "patch_validated")
    except Exception as e:
        state['final_status'] = "UNSAFE_REPAIR_REJECTED"
        state['error_message'] = str(e)
        logger.error(f"[Workflow] Patch validation failed: {e}")
        
    return state

def node_apply_patch(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] apply_patch - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    workspace_path = create_repair_workspace(state['analysis'].repository_url)
    state['workspace_path'] = workspace_path
    
    try:
        apply_patch_to_workspace(workspace_path, state['patch']['files_changed'])
        actual_diff = get_git_diff(workspace_path)
        # Store actual diff back into patch for the Reviewer
        state['patch']['actual_diff'] = actual_diff
        _persist_attempt_state(state, "patch_applied")
    except Exception as e:
        state['final_status'] = "REPAIR_FAILED"
        state['error_message'] = f"Failed to apply patch: {e}"
        logger.error(f"[Workflow] Patch application failed: {e}")
        
    return state

def node_run_reproduction(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] run_reproduction - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    repro = state['reproduction']
    analysis = state['analysis']
    workspace_path = state['workspace_path']
    
    test_file_path = "fixyron_reproduction_test.py" if repro.test_framework == "pytest" else "fixyron_reproduction.test.js"
    full_test_path = os.path.join(workspace_path, test_file_path)
    with open(full_test_path, "w", encoding="utf-8") as f:
        f.write(repro.test_code)
        
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
    
    state['reproduction_result'] = {
        "exit_code": result_dict.get("exit_code", 1),
        "stdout": result_dict.get("stdout", ""),
        "stderr": result_dict.get("stderr", result_dict.get("error_message", "")),
        "status": "passed" if result_dict.get("status") == "success" else "failed",
        "duration_ms": result_dict.get("duration_ms", 0)
    }
    
    _persist_attempt_state(state, "testing")
    return state

def node_run_regression_tests(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] run_regression_tests - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    # If reproduction didn't pass, we don't necessarily need to run regression, but we can anyway.
    # For Week 5, we'll run the full suite if it's available.
    analysis = state['analysis']
    if analysis.test_framework == "pytest":
        command = "pytest"
    else:
        command = "pytest" # fallback
        
    result_dict = run_tests_in_sandbox(
        workspace_dir=state['workspace_path'],
        language=analysis.primary_language,
        test_command=command,
        framework=analysis.test_framework,
        timeout_seconds=60
    )
    
    state['regression_result'] = {
        "exit_code": result_dict.get("exit_code", 1),
        "stdout": result_dict.get("stdout", ""),
        "stderr": result_dict.get("stderr", result_dict.get("error_message", "")),
        "status": "passed" if result_dict.get("status") == "success" else "failed",
        "duration_ms": result_dict.get("duration_ms", 0)
    }
    
    return state

def node_review_repair(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] review_repair - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    db = state['db_session']
    
    previous_attempts_records = db.query(RepairAttempt).filter(
        RepairAttempt.repair_id == state['repair_id'],
        RepairAttempt.attempt_number < state['current_attempt_num']
    ).order_by(RepairAttempt.attempt_number.asc()).all()
    
    previous_attempts = [
        {
            "attempt": a.attempt_number,
            "strategy": a.strategy,
            "patch": a.patch,
            "review": a.review
        } for a in previous_attempts_records
    ]

    agent = ReviewerAgent()
    review = agent.evaluate_attempt(
        bug_description=state['reproduction'].bug_description,
        diagnosis={
            "root_cause": state['diagnosis'].root_cause,
            "failure_mechanism": state['diagnosis'].failure_mechanism,
        },
        patch=state['patch'].get('actual_diff', ''),
        reproduction_result=state['reproduction_result'],
        regression_result=state['regression_result'],
        previous_attempts=previous_attempts
    )
    
    state['reviewer_output'] = review.model_dump()
    if review.verdict == 'INCONCLUSIVE':
        state['final_status'] = 'INCONCLUSIVE'
        
    _persist_attempt_state(state, "reviewed")
    return state

def node_analyze_failure(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] analyze_failure - Attempt {state['current_attempt_num']}")
    # Clean up workspace since attempt is done
    if state.get('workspace_path'):
        cleanup_repair_workspace(state['workspace_path'])
        state['workspace_path'] = None
        
    db = state['db_session']
    attempt = db.query(RepairAttempt).filter(RepairAttempt.id == state['attempt_id']).first()
    if attempt:
        attempt.status = "failed"
        attempt.completed_at = datetime.now()
        db.commit()

    if state['current_attempt_num'] >= state['max_attempts']:
        state['final_status'] = "REPAIR_FAILED"
        state['error_message'] = "Maximum attempts reached."
        return state
        
    # Check for stalled progress
    if state['reviewer_output'].get('recommended_action') == 'STOP':
        state['final_status'] = "REPAIR_STALLED"
        return state
        
    return state

def node_plan_next_attempt(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] plan_next_attempt - Attempt {state['current_attempt_num']}")
    if state.get('final_status'): return state
    
    agent = PlannerAgent()
    plan = agent.plan_next_attempt(
        original_diagnosis={
            "root_cause": state['diagnosis'].root_cause,
            "failure_mechanism": state['diagnosis'].failure_mechanism,
            "affected_files": state['diagnosis'].affected_files
        },
        code_contexts=state['code_contexts'],
        failed_attempt={
            "patch": state['patch'].get('actual_diff', ''),
            "review": state['reviewer_output']
        }
    )
    
    state['planner_strategy'] = plan.model_dump()
    
    # We now increment and start over in logic
    state['current_attempt_num'] += 1
    
    db = state['db_session']
    repair = db.query(Repair).filter(Repair.id == state['repair_id']).first()
    repair.current_attempt = state['current_attempt_num']
    
    attempt = RepairAttempt(
        repair_id=repair.id,
        attempt_number=state['current_attempt_num'],
        status="pending",
        strategy=state['planner_strategy']
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    state['attempt_id'] = attempt.id
    # Reset for next run
    state['patch'] = None
    state['reproduction_result'] = None
    state['regression_result'] = None
    state['reviewer_output'] = None
    
    return state

def node_final_verification(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] final_verification - Attempt {state['current_attempt_num']}")
    
    db = state['db_session']
    attempt = db.query(RepairAttempt).filter(RepairAttempt.id == state['attempt_id']).first()
    if attempt:
        attempt.status = "passed"
        attempt.completed_at = datetime.now()
        db.commit()
        
    # In a full system, we might run an even more thorough suite here
    # For now, if we reach this point, the Reviewer passed it.
    
    state['final_status'] = "VERIFIED_FIXED"
    state['verification_status'] = "passed"
    
    if state.get('workspace_path'):
        cleanup_repair_workspace(state['workspace_path'])
        state['workspace_path'] = None
        
    return state

def node_finalize(state: RepairState) -> RepairState:
    logger.info(f"[Workflow] finalize - Status: {state.get('final_status')}")
    db = state['db_session']
    repair = db.query(Repair).filter(Repair.id == state['repair_id']).first()
    if repair:
        repair.final_status = state.get('final_status', 'INCONCLUSIVE')
        repair.status = "completed"
        repair.error_message = state.get('error_message')
        repair.completed_at = datetime.now()
        
        # Pull final stats from attempt
        attempt = db.query(RepairAttempt).filter(RepairAttempt.id == state['attempt_id']).first()
        if attempt:
            repair.patch = attempt.patch
            repair.test_result = attempt.reproduction_result
            repair.summary = attempt.review.get('summary') if attempt.review else ""
            repair.confidence = attempt.review.get('confidence') if attempt.review else 0.0
            
            if attempt.patch and 'actual_diff' in attempt.patch:
                added = sum(1 for line in attempt.patch['actual_diff'].splitlines() if line.startswith("+") and not line.startswith("+++"))
                removed = sum(1 for line in attempt.patch['actual_diff'].splitlines() if line.startswith("-") and not line.startswith("---"))
                repair.lines_added = added
                repair.lines_removed = removed
                repair.files_changed = len(attempt.patch.get('files_changed', []))

        db.commit()
    
    return state

def route_decision(state: RepairState) -> str:
    if state.get('final_status'):
        return "finalize"
        
    review = state.get('reviewer_output', {})
    verdict = review.get('verdict', 'INCONCLUSIVE')
    
    if verdict == 'PASS':
        return "final_verification"
    elif verdict == 'INCONCLUSIVE':
        return "finalize"
    else:
        return "analyze_failure"
        
def route_replan(state: RepairState) -> str:
    if state.get('final_status'):
        return "finalize"
    return "plan_next_attempt"


def run_repair_workflow(repair_id: str):
    logger.info(f"Starting repair workflow for {repair_id}")
    db = SessionLocal()
    try:
        state = RepairState(
            repair_id=repair_id,
            db_session=db,
            analysis=None,
            reproduction=None,
            diagnosis=None,
            code_contexts=[],
            current_attempt_num=0,
            max_attempts=3,
            attempt_id="",
            planner_strategy=None,
            patch=None,
            workspace_path=None,
            reproduction_result=None,
            regression_result=None,
            reviewer_output=None,
            final_status="",
            error_message=None
        )
        
        current_node = "load_repair_context"
        
        while current_node != "END":
            logger.info(f"[StateMachine] Executing node: {current_node}")
            
            if current_node == "load_repair_context":
                state = node_load_repair_context(state)
                current_node = "generate_patch"
                
            elif current_node == "generate_patch":
                state = node_generate_patch(state)
                current_node = "validate_patch"
                
            elif current_node == "validate_patch":
                state = node_validate_patch(state)
                current_node = "apply_patch"
                
            elif current_node == "apply_patch":
                state = node_apply_patch(state)
                current_node = "run_reproduction"
                
            elif current_node == "run_reproduction":
                state = node_run_reproduction(state)
                current_node = "run_regression_tests"
                
            elif current_node == "run_regression_tests":
                state = node_run_regression_tests(state)
                current_node = "review_repair"
                
            elif current_node == "review_repair":
                state = node_review_repair(state)
                current_node = route_decision(state)
                
            elif current_node == "analyze_failure":
                state = node_analyze_failure(state)
                current_node = route_replan(state)
                
            elif current_node == "plan_next_attempt":
                state = node_plan_next_attempt(state)
                current_node = "generate_patch"
                
            elif current_node == "final_verification":
                state = node_final_verification(state)
                current_node = "finalize"
                
            elif current_node == "finalize":
                state = node_finalize(state)
                current_node = "END"
                
            else:
                logger.error(f"Unknown node: {current_node}")
                break
                
            if state.get('final_status') and current_node not in ["finalize", "END"]:
                current_node = "finalize"
                
    except Exception as e:
        logger.error(f"Workflow failed for {repair_id}: {e}", exc_info=True)
        # Attempt to mark as failed
        repair = db.query(Repair).filter(Repair.id == repair_id).first()
        if repair:
            repair.final_status = "REPAIR_FAILED"
            repair.error_message = str(e)
            db.commit()
    finally:
        db.close()
