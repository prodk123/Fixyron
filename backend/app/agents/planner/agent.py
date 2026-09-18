import os
import json
import re
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from app.agents.planner.schemas import PlannerOutput
from app.agents.planner.prompts import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
MAX_RETRIES = 4

def _extract_json_from_text(text: str) -> Optional[dict]:
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

def _coerce_planner(result_dict: dict) -> PlannerOutput:
    cleaned = {}
    for k, v in result_dict.items():
        cleaned[k.lstrip('.')] = v
    result_dict = cleaned

    required_keys = {"strategy", "files_to_inspect"}
    if required_keys.issubset(result_dict.keys()):
        return PlannerOutput.model_validate(result_dict)

    for key, value in result_dict.items():
        if isinstance(value, dict) and required_keys.issubset(value.keys()):
            return PlannerOutput.model_validate(value)

    for candidate_key in ["plan", "planner", "result", "output", "response"]:
        if candidate_key in result_dict and isinstance(result_dict[candidate_key], dict):
            nested = result_dict[candidate_key]
            if required_keys.issubset(nested.keys()):
                return PlannerOutput.model_validate(nested)

    raise ValueError(f"Cannot coerce LLM output to PlannerOutput. Keys found: {list(result_dict.keys())}")


class PlannerAgent:
    def plan_next_attempt(
        self,
        original_diagnosis: Dict[str, Any],
        code_contexts: list,
        failed_attempt: Dict[str, Any]
    ) -> PlannerOutput:
        
        context_str = f"## Original Diagnosis\n{json.dumps(original_diagnosis, indent=2)}\n\n"
        context_str += f"## Code Context\n"
        for cc in code_contexts:
            context_str += f"--- {cc.get('file')} ---\n{cc.get('content')}\n\n"
        
        context_str += f"## Failed Attempt Patch\n```diff\n{failed_attempt.get('patch', 'N/A')}\n```\n\n"
        
        review = failed_attempt.get('review', {})
        context_str += f"## Reviewer Feedback\n"
        context_str += f"Verdict: {review.get('verdict', 'N/A')}\n"
        context_str += f"Failure Category: {review.get('failure_category', 'N/A')}\n"
        context_str += f"Summary: {review.get('summary', 'N/A')}\n"
        context_str += f"Reason: {review.get('reason', 'N/A')}\n\n"

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": context_str}
        ]

        schema_str = json.dumps(PlannerOutput.model_json_schema(), indent=2)
        messages[0]["content"] += f"\n\n## Required Output Schema\nReturn your plan as a single JSON object matching this schema:\n```json\n{schema_str}\n```"

        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", None)
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not api_key:
            raise Exception("LLM configuration missing: LLM_API_KEY not set")

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                logger.info(f"[PlannerAgent] attempt {attempt + 1}/{MAX_RETRIES + 1} using model={model}")
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )

                result_text = response.choices[0].message.content
                if not result_text:
                    raise ValueError("LLM returned empty response")
                
                logger.info(f"[PlannerAgent] raw output (first 300 chars): {result_text[:300]}")
                parsed_json = _extract_json_from_text(result_text)
                if parsed_json is None:
                    raise ValueError(f"Could not extract JSON: {result_text[:200]}")

                return _coerce_planner(parsed_json)
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    logger.warning(f"[PlannerAgent] LLM generation failed on attempt {attempt+1}. Retrying... Error: {str(e)}")
                    continue
        
        raise Exception(f"PlannerAgent failed after {MAX_RETRIES + 1} attempts: {str(last_exception)}")
