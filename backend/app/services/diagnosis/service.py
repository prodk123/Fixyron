"""
Diagnosis service — orchestrates the complete diagnosis workflow.
Ties together context building, agent execution, evidence validation, and persistence.
"""
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt
from app.db.models.diagnosis import Diagnosis
from app.services.repository.clone import clone_repository, cleanup_workspace
from app.services.diagnosis.context_builder import build_diagnosis_context
from app.services.diagnosis.evidence_validator import (
    validate_affected_files,
    validate_affected_functions,
    validate_confidence,
    classify_confidence,
    contains_code_patch,
    validate_evidence,
    compute_confidence_adjustment,
)
from app.agents.diagnosis.agent import run_diagnosis_agent

logger = logging.getLogger(__name__)


def perform_diagnosis(db: Session, diagnosis_id: str) -> Diagnosis:
    """
    Execute the complete diagnosis workflow:
    1. Load analysis + reproduction from DB
    2. Clone repository
    3. Build diagnosis context
    4. Run diagnosis agent
    5. Validate diagnosis
    6. Persist results
    7. Cleanup
    """
    diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
    if not diagnosis:
        raise ValueError("Diagnosis record not found")

    analysis = db.query(RepositoryAnalysis).filter(
        RepositoryAnalysis.id == diagnosis.analysis_id
    ).first()
    if not analysis:
        _fail_diagnosis(db, diagnosis, "Analysis not found")
        return diagnosis

    reproduction = db.query(ReproductionAttempt).filter(
        ReproductionAttempt.id == diagnosis.reproduction_id
    ).first()
    if not reproduction:
        _fail_diagnosis(db, diagnosis, "Reproduction attempt not found")
        return diagnosis

    # Verify reproduction has evidence
    if not reproduction.evidence:
        _fail_diagnosis(db, diagnosis, "Reproduction has no evidence")
        return diagnosis

    workspace_dir = None

    try:
        # Step 1: Collecting context
        _update_status(db, diagnosis, "collecting_context")

        workspace_dir = clone_repository(analysis.repository_url)
        if not workspace_dir:
            _fail_diagnosis(db, diagnosis, "Failed to clone repository")
            return diagnosis

        context = build_diagnosis_context(
            db=db,
            analysis=analysis,
            reproduction=reproduction,
            workspace_dir=workspace_dir,
        )

        # Store code context in the diagnosis record
        diagnosis.code_context = context.code_contexts
        db.commit()

        # Step 2: Analyzing
        _update_status(db, diagnosis, "analyzing")

        model_name = os.getenv("LLM_MODEL", "unknown")
        diagnosis.model = model_name

        result = run_diagnosis_agent(context)

        # Step 3: Validating
        _update_status(db, diagnosis, "validating")

        # Validate affected files
        valid_files, hallucinated_files = validate_affected_files(
            result.affected_files, workspace_dir
        )
        if hallucinated_files:
            logger.warning(f"Hallucinated files detected: {hallucinated_files}")

        # Validate affected functions
        found_funcs, not_found_funcs = validate_affected_functions(
            result.affected_functions, valid_files, workspace_dir
        )

        # Check for code patches in the diagnosis
        has_patch = contains_code_patch(result.root_cause) or contains_code_patch(result.failure_mechanism)
        if has_patch:
            logger.warning("Diagnosis contains code patch content")

        # Validate evidence
        validated_evidence = validate_evidence(
            [e.model_dump() for e in result.evidence]
        )

        # Compute adjusted confidence
        raw_confidence = validate_confidence(result.confidence)
        adjusted_confidence = compute_confidence_adjustment(
            hallucinated_files=hallucinated_files,
            not_found_functions=not_found_funcs,
            has_patch=has_patch,
            original_confidence=raw_confidence,
        )

        # Step 4: Persist
        diagnosis.summary = result.summary
        diagnosis.root_cause = result.root_cause
        diagnosis.failure_mechanism = result.failure_mechanism
        diagnosis.affected_files = valid_files  # Only validated files
        diagnosis.affected_functions = result.affected_functions
        diagnosis.evidence = validated_evidence
        diagnosis.alternative_causes = [ac.model_dump() for ac in result.alternative_causes] if result.alternative_causes else []
        diagnosis.confidence = adjusted_confidence
        diagnosis.confidence_level = classify_confidence(adjusted_confidence)

        # Determine final status
        if adjusted_confidence < 0.3 or not result.root_cause.strip():
            diagnosis.status = "inconclusive"
            if hallucinated_files:
                diagnosis.error_message = f"Low confidence: hallucinated files {hallucinated_files}"
        else:
            diagnosis.status = "completed"

        diagnosis.completed_at = datetime.now()
        db.commit()

        logger.info(
            f"Diagnosis {diagnosis_id} completed: "
            f"status={diagnosis.status}, confidence={adjusted_confidence:.2f}, "
            f"level={diagnosis.confidence_level}"
        )

    except Exception as e:
        logger.error(f"Diagnosis {diagnosis_id} failed: {e}")
        _fail_diagnosis(db, diagnosis, str(e))
    finally:
        if workspace_dir:
            cleanup_workspace(workspace_dir)

    return diagnosis


def _update_status(db: Session, diagnosis: Diagnosis, status: str):
    """Update diagnosis status and commit."""
    diagnosis.status = status
    db.commit()
    logger.info(f"Diagnosis {diagnosis.id} status → {status}")


def _fail_diagnosis(db: Session, diagnosis: Diagnosis, error_message: str):
    """Mark diagnosis as failed."""
    diagnosis.status = "failed"
    diagnosis.error_message = error_message
    diagnosis.completed_at = datetime.now()
    db.commit()
    logger.error(f"Diagnosis {diagnosis.id} failed: {error_message}")
