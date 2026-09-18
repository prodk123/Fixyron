# Week 3 Architecture: Bug Diagnosis Agent

## Overview

Week 3 introduces the Bug Diagnosis Agent, which takes the reproduction evidence from Week 2 and produces a structured, evidence-backed root cause analysis of the defect.

The system is designed to be read-only, avoiding any code modification, and is strictly fortified against hallucination and prompt injection.

## Data Model

The `Diagnosis` model (`app.db.models.diagnosis`) stores:
- **References**: `analysis_id`, `reproduction_id`
- **Output**: `summary`, `root_cause`, `failure_mechanism`
- **Structured JSON**: `affected_files`, `affected_functions`, `evidence`, `alternative_causes`, `code_context`
- **Metadata**: `confidence`, `confidence_level`, `status`

## Diagnosis Workflow

The workflow is orchestrated by `perform_diagnosis` in `app/services/diagnosis/service.py` as a linear state machine:

1. **collecting_context**: The repository is cloned. The context builder (`app/services/diagnosis/context_builder.py`) extracts the stack trace and retrieves relevant code using a scoring system (`app/services/diagnosis/code_retriever.py`).
2. **analyzing**: The LLM agent (`app/agents/diagnosis/agent.py`) is invoked with strict anti-hallucination prompts and a Pydantic JSON schema.
3. **validating**: The evidence validator (`app/services/diagnosis/evidence_validator.py`) deterministically checks that cited files exist, functions exist in those files, and no patch code was generated. Confidence scores are downgraded for violations.
4. **completed / inconclusive / failed**: The diagnosis is finalized based on validation results and confidence thresholds.

## Security & Reliability

- **Prompt Injection Defense**: Repository content is explicitly labeled as untrusted data in the system prompt.
- **Hallucination Mitigation**: Post-LLM validation cross-references cited files/functions against the actual filesystem using `os.walk` and regex.
- **Context Window Management**: The `code_retriever` uses a token/character budget to prioritize the stack trace and reproduction test target files.

## Frontend Integration

The diagnosis results are displayed in a detailed, read-only panel on the Analysis page (`app/analysis/[id]/page.tsx`). The panel includes:
- A timeline tracking the state machine (`pending` -> `completed`).
- Expandable code viewers showing the exact context the LLM used.
- Confidence badges and categorized evidence items.
