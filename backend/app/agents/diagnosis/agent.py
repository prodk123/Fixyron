"""
FIXYRON Bug Diagnosis Agent.
Uses structured LLM interaction to produce evidence-backed diagnosis.
"""
import os
import json
import re
import logging
from typing import Optional
from openai import OpenAI

from app.agents.diagnosis.schemas import DiagnosisOutput
from app.agents.diagnosis.prompts import DIAGNOSIS_SYSTEM_PROMPT, build_diagnosis_prompt
from app.services.diagnosis.context_builder import DiagnosisContext

logger = logging.getLogger(__name__)

MAX_RETRIES = 4


def _extract_json_from_text(text: str) -> Optional[dict]:
    """Try multiple strategies to extract a valid JSON object from LLM output."""
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    patterns = [
        r'```json\s*\n?(.*?)\n?\s*```',
        r'```\s*\n?(.*?)\n?\s*```',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find first { ... } block
    depth = 0
    start = None
    for i, c in enumerate(text):
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    start = None

    return None


def _coerce_diagnosis(result_dict: dict) -> DiagnosisOutput:
    """
    Try to coerce a possibly-malformed dict into a DiagnosisOutput.
    The small model sometimes returns file paths as top-level keys instead
    of the expected schema fields.
    """
    # If it already has the right top-level keys, just validate
    required_keys = {"summary", "root_cause", "failure_mechanism", "confidence"}
    if required_keys.issubset(result_dict.keys()):
        return DiagnosisOutput(**result_dict)

    # Check if there's a nested object that has the right shape
    for key, value in result_dict.items():
        if isinstance(value, dict) and required_keys.issubset(value.keys()):
            return DiagnosisOutput(**value)

    # If the model returned something like {"diagnosis": {...}}
    for candidate_key in ["diagnosis", "result", "output", "response"]:
        if candidate_key in result_dict and isinstance(result_dict[candidate_key], dict):
            nested = result_dict[candidate_key]
            if required_keys.issubset(nested.keys()):
                return DiagnosisOutput(**nested)

    # Last resort: raise so we retry
    raise ValueError(f"Cannot coerce LLM output to DiagnosisOutput. Keys found: {list(result_dict.keys())}")


def run_diagnosis_agent(context: DiagnosisContext) -> DiagnosisOutput:
    """
    Execute the diagnosis agent against the assembled context.
    Uses the existing LLM configuration (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL).
    Retries up to MAX_RETRIES times on malformed output.
    """
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", None)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        raise Exception("LLM configuration missing: LLM_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

    # Build the user prompt from context
    user_prompt = build_diagnosis_prompt(context)

    # Include a concrete example in the prompt to guide smaller models
    example = json.dumps({
        "summary": "The divide function does not handle zero denominators",
        "root_cause": "The divide() function in calculator.py performs a / b without checking if b is zero",
        "affected_files": ["calculator.py"],
        "affected_functions": ["divide"],
        "failure_mechanism": "When b=0, Python raises ZeroDivisionError instead of the expected ValueError",
        "evidence": [{"type": "source_location", "file": "calculator.py", "line": 3, "description": "No zero check before division"}],
        "confidence": 0.95,
        "alternative_causes": []
    }, indent=2)

    # Include the JSON schema in the prompt
    schema_str = json.dumps(DiagnosisOutput.model_json_schema(), indent=2)
    user_prompt += f"\n\n## Required Output Schema\nReturn your diagnosis as a single JSON object matching this schema:\n```json\n{schema_str}\n```"
    user_prompt += f"\n\n## Example Output\nHere is an example of the expected output format:\n```json\n{example}\n```"
    user_prompt += "\n\nIMPORTANT: Return ONLY the JSON object. Do not wrap it in markdown code blocks. Do not return file paths as keys. Return a flat JSON object with the fields: summary, root_cause, affected_files, affected_functions, failure_mechanism, evidence, confidence, alternative_causes."

    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.info(f"Diagnosis agent attempt {attempt + 1}/{MAX_RETRIES + 1} using model={model}")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Lower temperature for more consistent output
            )

            result_text = response.choices[0].message.content
            if not result_text:
                raise ValueError("LLM returned empty response")

            logger.info(f"Diagnosis raw output (first 300 chars): {result_text[:300]}")

            result_dict = _extract_json_from_text(result_text)
            if result_dict is None:
                raise ValueError(f"Could not extract JSON from LLM response: {result_text[:200]}")

            # Validate against Pydantic schema (with coercion)
            diagnosis = _coerce_diagnosis(result_dict)

            # Basic sanity checks
            if not diagnosis.root_cause or not diagnosis.root_cause.strip():
                raise ValueError("Diagnosis root_cause is empty")

            if not diagnosis.summary or not diagnosis.summary.strip():
                raise ValueError("Diagnosis summary is empty")

            logger.info(f"Diagnosis agent succeeded on attempt {attempt + 1}")
            return diagnosis

        except json.JSONDecodeError as e:
            logger.warning(f"Diagnosis attempt {attempt + 1} failed: invalid JSON — {e}")
            last_error = e
        except Exception as e:
            logger.warning(f"Diagnosis attempt {attempt + 1} failed: {e}")
            last_error = e

    # All retries exhausted
    raise Exception(f"Diagnosis agent failed after {MAX_RETRIES + 1} attempts: {last_error}")

