import os
import json
import re
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Pydantic schema for the LLM output
class ReproductionTestSchema(BaseModel):
    test_framework: str = Field(description="The testing framework to use, e.g., pytest, jest")
    test_file_path: str = Field(description="The relative path where the test should be saved, e.g., tests/test_reproduction.py")
    test_code: str = Field(description="The complete source code of the reproduction test")
    target_files: List[str] = Field(description="List of files this test targets")
    target_functions: List[str] = Field(description="List of functions this test targets")
    hypothesis: str = Field(description="Hypothesis of what the bug is and how this test reproduces it")
    expected_behavior: str = Field(description="What should happen if the bug is fixed")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")


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

def _coerce_reproduction(result_dict: dict) -> ReproductionTestSchema:
    cleaned = {}
    for k, v in result_dict.items():
        cleaned[k.lstrip('.')] = v
    result_dict = cleaned

    required_keys = {"test_framework", "test_file_path", "test_code"}
    if required_keys.issubset(result_dict.keys()):
        return ReproductionTestSchema(**result_dict)

    for key, value in result_dict.items():
        if isinstance(value, dict) and required_keys.issubset(value.keys()):
            return ReproductionTestSchema(**value)

    for candidate_key in ["reproduction", "test", "result", "output"]:
        if candidate_key in result_dict and isinstance(result_dict[candidate_key], dict):
            nested = result_dict[candidate_key]
            if required_keys.issubset(nested.keys()):
                return ReproductionTestSchema(**nested)

    raise ValueError(f"Cannot coerce to ReproductionTestSchema. Keys: {list(result_dict.keys())}")


def generate_reproduction_test(
    bug_description: str,
    primary_language: str,
    test_framework: str,
    context_files: Dict[str, str],
) -> Dict[str, Any]:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", None)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        logger.warning("No LLM_API_KEY provided. Cannot generate test.")
        raise Exception("LLM configuration missing")

    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

    # Format context files
    context_str = ""
    for path, content in context_files.items():
        context_str += f"\n--- {path} ---\n{content}\n"

    schema_str = json.dumps(ReproductionTestSchema.model_json_schema(), indent=2)
    example = json.dumps({
        "test_framework": "pytest",
        "test_file_path": "tests/test_reproduction.py",
        "test_code": "import pytest\nfrom calculator import divide\n\ndef test_divide_by_zero():\n    with pytest.raises(ValueError, match='Cannot divide by zero'):\n        divide(10, 0)\n",
        "target_files": ["calculator.py"],
        "target_functions": ["divide"],
        "hypothesis": "The divide function raises ZeroDivisionError instead of ValueError",
        "expected_behavior": "Should raise ValueError",
        "confidence": 0.95
    }, indent=2)

    prompt = f"""
You are generating a software reproduction test for a {primary_language} project using {test_framework}.

Do not fix the bug.
Do not modify production code.
Do not invent APIs that are not present in the repository.
Use the repository's existing testing conventions.

Your goal is to create a minimal deterministic test that demonstrates the reported failure if the bug exists.

Bug Description:
{bug_description}

Relevant Source Context:
{context_str}

Return a structured JSON response matching this JSON schema:
```json
{schema_str}
```

Example output format:
```json
{example}
```

IMPORTANT: Return ONLY the JSON object. Do not wrap it in markdown block if possible. No file paths as keys.
"""

    MAX_RETRIES = 4
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.info(f"Generating reproduction test (attempt {attempt+1}/{MAX_RETRIES+1})")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a senior QA engineer. Output strictly in the requested JSON format."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content
            if not result_text:
                raise ValueError("LLM returned empty")
            
            logger.info(f"Raw reproduction output (first 200 chars): {result_text[:200]}")
            result_dict = _extract_json_from_text(result_text)
            if not result_dict:
                raise ValueError(f"Could not extract JSON: {result_text[:100]}")

            validated = _coerce_reproduction(result_dict)
            return validated.model_dump()
            
        except Exception as e:
            last_error = e
            logger.warning(f"Reproduction generation attempt {attempt+1} failed: {e}")

    logger.error(f"LLM generation failed after {MAX_RETRIES+1} attempts.")
    raise last_error
