import os
import json
import re
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from app.agents.reviewer.schemas import ReviewerOutput
from app.agents.reviewer.prompts import REVIEWER_SYSTEM_PROMPT

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

def _coerce_review(result_dict: dict) -> ReviewerOutput:
    cleaned = {}
    for k, v in result_dict.items():
        cleaned[k.lstrip('.')] = v
    result_dict = cleaned

    required_keys = {"verdict", "bug_resolved", "summary", "reason"}
    if required_keys.issubset(result_dict.keys()):
        return ReviewerOutput.model_validate(result_dict)

    for key, value in result_dict.items():
        if isinstance(value, dict) and required_keys.issubset(value.keys()):
            return ReviewerOutput.model_validate(value)

    for candidate_key in ["review", "reviewer", "result", "output", "response"]:
        if candidate_key in result_dict and isinstance(result_dict[candidate_key], dict):
            nested = result_dict[candidate_key]
            if required_keys.issubset(nested.keys()):
                return ReviewerOutput.model_validate(nested)

    raise ValueError(f"Cannot coerce LLM output to ReviewerOutput. Keys found: {list(result_dict.keys())}")


class ReviewerAgent:
    def evaluate_attempt(
        self,
        bug_description: str,
        diagnosis: Dict[str, Any],
        patch: str,
        reproduction_result: Dict[str, Any],
        regression_result: Optional[Dict[str, Any]],
        previous_attempts: list
    ) -> ReviewerOutput:
        
        context_str = f"## Original Bug Description\n{bug_description}\n\n"
        context_str += f"## Original Diagnosis\n{json.dumps(diagnosis, indent=2)}\n\n"
        context_str += f"## Candidate Patch\n```diff\n{patch}\n```\n\n"
        
        context_str += f"## Reproduction Test Result\n"
        context_str += f"Status: {reproduction_result.get('status')}\n"
        context_str += f"Exit Code: {reproduction_result.get('exit_code')}\n"
        context_str += f"Output:\n{reproduction_result.get('stdout', '')}\n"
        context_str += f"Error:\n{reproduction_result.get('stderr', '')}\n\n"

        if regression_result:
            context_str += f"## Regression Test Result\n"
            context_str += f"Status: {regression_result.get('status')}\n"
            context_str += f"Exit Code: {regression_result.get('exit_code')}\n"
            context_str += f"Output:\n{regression_result.get('stdout', '')}\n"
            context_str += f"Error:\n{regression_result.get('stderr', '')}\n\n"

        if previous_attempts:
            context_str += f"## Previous Failed Attempts\n"
            for i, attempt in enumerate(previous_attempts, 1):
                context_str += f"Attempt {i}:\n"
                context_str += f"Strategy: {attempt.get('strategy', {}).get('strategy', 'N/A')}\n"
                context_str += f"Reviewer Feedback: {attempt.get('review', {}).get('reason', 'N/A')}\n\n"

        messages = [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": context_str}
        ]

        schema_str = json.dumps(ReviewerOutput.model_json_schema(), indent=2)
        messages[0]["content"] += f"\n\n## Required Output Schema\nReturn your review as a single JSON object matching this schema:\n```json\n{schema_str}\n```"

        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", None)
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not api_key:
            raise Exception("LLM configuration missing: LLM_API_KEY not set")

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                logger.info(f"[ReviewerAgent] attempt {attempt + 1}/{MAX_RETRIES + 1} using model={model}")
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

                result_text = response.choices[0].message.content
                if not result_text:
                    raise ValueError("LLM returned empty response")
                
                logger.info(f"[ReviewerAgent] raw output (first 300 chars): {result_text[:300]}")
                parsed_json = _extract_json_from_text(result_text)
                if parsed_json is None:
                    raise ValueError(f"Could not extract JSON: {result_text[:200]}")

                return _coerce_review(parsed_json)
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    logger.warning(f"[ReviewerAgent] LLM generation failed on attempt {attempt+1}. Retrying... Error: {str(e)}")
                    continue
        
        raise Exception(f"ReviewerAgent failed after {MAX_RETRIES + 1} attempts: {str(last_exception)}")
