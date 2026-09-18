import os
import json
import re
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from app.agents.repair.schemas import RepairOutput
from app.agents.repair.prompts import REPAIR_SYSTEM_PROMPT
from app.agents.repair.context import build_repair_context

logger = logging.getLogger(__name__)
MAX_RETRIES = 4


def _extract_json_from_text(text: str) -> Optional[dict]:
    """Try multiple strategies to extract a valid JSON object from LLM output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for pattern in [r'```json\s*\n?(.*?)\n?\s*```', r'```\s*\n?(.*?)\n?\s*```']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

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


def _coerce_repair(result_dict: dict) -> RepairOutput:
    """Try to coerce a possibly-malformed dict into RepairOutput."""
    # Fix dot-prefixed keys (small model quirk: ".summary" instead of "summary")
    cleaned = {}
    for k, v in result_dict.items():
        cleaned[k.lstrip('.')] = v
    result_dict = cleaned

    required_keys = {"summary", "files_changed", "confidence"}
    if required_keys.issubset(result_dict.keys()):
        return RepairOutput.model_validate(result_dict)

    for key, value in result_dict.items():
        if isinstance(value, dict) and required_keys.issubset(value.keys()):
            return RepairOutput.model_validate(value)

    for candidate_key in ["repair", "patch", "result", "output", "response"]:
        if candidate_key in result_dict and isinstance(result_dict[candidate_key], dict):
            nested = result_dict[candidate_key]
            if required_keys.issubset(nested.keys()):
                return RepairOutput.model_validate(nested)

    raise ValueError(f"Cannot coerce LLM output to RepairOutput. Keys found: {list(result_dict.keys())}")


class RepairAgent:
    def __init__(self):
        pass

    def generate_repair(
        self,
        bug_description: str,
        reproduction_evidence: list,
        diagnosis: Dict[str, Any],
        code_contexts: list,
        planner_strategy: Optional[Dict[str, Any]] = None,
        previous_attempts: Optional[list] = None
    ) -> RepairOutput:
        
        context_str = build_repair_context(
            bug_description,
            reproduction_evidence,
            diagnosis,
            code_contexts,
            planner_strategy,
            previous_attempts
        )
        
        # Include a concrete example to guide smaller models
        example = json.dumps({
            "summary": "Add zero-denominator check to divide()",
            "reasoning_summary": "The divide function needs to check if b is zero before performing division and raise ValueError instead.",
            "expected_effect": "divide(10, 0) will raise ValueError('Cannot divide by zero') instead of ZeroDivisionError.",
            "confidence": 0.95,
            "files_changed": [{
                "path": "calculator.py",
                "operation": "modify",
                "patch": "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,3 +1,5 @@\n def divide(a, b):\n+    if b == 0:\n+        raise ValueError(\"Cannot divide by zero\")\n     return a / b"
            }]
        }, indent=2)

        messages = [
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": context_str}
        ]

        # Include the JSON schema in the prompt
        schema_str = json.dumps(RepairOutput.model_json_schema(), indent=2)
        messages[0]["content"] += f"\n\n## Required Output Schema\nReturn your patch as a single JSON object matching this schema:\n```json\n{schema_str}\n```"
        messages[0]["content"] += f"\n\n## Example Output\n```json\n{example}\n```"
        messages[0]["content"] += "\n\nIMPORTANT: Return ONLY the JSON object. Do not return file paths as keys. The JSON must have these top-level fields: summary, reasoning_summary, expected_effect, confidence, files_changed."

        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", None)
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not api_key:
            raise Exception("LLM configuration missing: LLM_API_KEY not set")

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        last_exception = None
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                logger.info(f"[RepairAgent] attempt {attempt + 1}/{MAX_RETRIES + 1} using model={model}")

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

                result_text = response.choices[0].message.content
                if not result_text:
                    raise ValueError("LLM returned empty response")

                logger.info(f"[RepairAgent] raw output (first 300 chars): {result_text[:300]}")
                
                parsed_json = _extract_json_from_text(result_text)
                if parsed_json is None:
                    raise ValueError(f"Could not extract JSON from LLM response: {result_text[:200]}")

                return _coerce_repair(parsed_json)
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    logger.warning(f"[RepairAgent] LLM generation failed on attempt {attempt+1}. Retrying... Error: {str(e)}")
                    continue
        
        raise Exception(f"RepairAgent failed after {MAX_RETRIES + 1} attempts: {str(last_exception)}")

