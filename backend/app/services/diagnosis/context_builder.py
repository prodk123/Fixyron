"""
Context builder for the diagnosis agent.
Assembles all evidence from DB and workspace into a structured context
that the LLM can reason about.
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models.repository import RepositoryAnalysis
from app.db.models.qa import ReproductionAttempt
from app.services.diagnosis.stack_trace_parser import parse_stack_trace, ParsedStackTrace
from app.services.diagnosis.code_retriever import (
    rank_files, retrieve_code_contexts, CodeContext, RankedFile
)

logger = logging.getLogger(__name__)


class DiagnosisContext(BaseModel):
    """Complete context assembled for the diagnosis agent."""
    # Repository metadata
    repository_url: str
    repository_name: Optional[str] = None
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    test_framework: Optional[str] = None

    # Bug info
    bug_description: str

    # Reproduction evidence
    reproduction_classification: str
    reproduction_hypothesis: Optional[str] = None
    reproduction_test_code: Optional[str] = None
    reproduction_evidence: Optional[Dict[str, Any]] = None

    # Parsed stack trace
    stack_trace: Optional[ParsedStackTrace] = None
    raw_stack_trace: Optional[str] = None

    # Code contexts
    ranked_files: List[Dict[str, Any]] = []
    code_contexts: List[Dict[str, Any]] = []


def build_diagnosis_context(
    db: Session,
    analysis: RepositoryAnalysis,
    reproduction: ReproductionAttempt,
    workspace_dir: str,
) -> DiagnosisContext:
    """
    Build the complete diagnosis context from database records and workspace.
    """
    logger.info(f"Building diagnosis context for analysis={analysis.id}, reproduction={reproduction.id}")

    # 1. Extract raw stack trace from reproduction evidence
    raw_stdout = ""
    if reproduction.evidence and isinstance(reproduction.evidence, dict):
        raw_stdout = reproduction.evidence.get("stdout", "")

    # 2. Parse stack trace
    stack_trace = parse_stack_trace(
        raw_stdout,
        language=analysis.primary_language or "Python"
    )

    # 3. Collect file paths from stack trace
    stack_trace_files = []
    stack_trace_lines: Dict[str, List[int]] = {}
    if stack_trace and stack_trace.frames:
        for frame in stack_trace.frames:
            stack_trace_files.append(frame.file)
            if frame.line:
                clean = frame.file.lstrip('./')
                if clean not in stack_trace_lines:
                    stack_trace_lines[clean] = []
                stack_trace_lines[clean].append(frame.line)

    # 4. Rank files
    ranked = rank_files(
        workspace_dir=workspace_dir,
        stack_trace_files=stack_trace_files,
        reproduction_target_files=reproduction.target_files,
        relevant_files=analysis.relevant_files,
        bug_description=reproduction.bug_description,
        max_files=8,
    )

    # 5. Retrieve focused code contexts
    code_contexts = retrieve_code_contexts(
        workspace_dir=workspace_dir,
        ranked_files=ranked,
        stack_trace_lines=stack_trace_lines,
        max_total_chars=15000,
    )

    # 6. Assemble context
    context = DiagnosisContext(
        repository_url=analysis.repository_url,
        repository_name=analysis.repository_name,
        primary_language=analysis.primary_language,
        framework=analysis.framework,
        test_framework=analysis.test_framework,
        bug_description=reproduction.bug_description,
        reproduction_classification=reproduction.classification,
        reproduction_hypothesis=reproduction.hypothesis,
        reproduction_test_code=reproduction.test_code,
        reproduction_evidence=reproduction.evidence,
        stack_trace=stack_trace,
        raw_stack_trace=raw_stdout[:5000] if raw_stdout else None,
        ranked_files=[rf.model_dump() for rf in ranked],
        code_contexts=[cc.model_dump() for cc in code_contexts],
    )

    logger.info(
        f"Diagnosis context built: {len(ranked)} ranked files, "
        f"{len(code_contexts)} code contexts, "
        f"stack_trace={'yes' if stack_trace else 'no'}"
    )

    return context
