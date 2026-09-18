"""
Evidence validator for diagnosis output.
Performs deterministic post-LLM validation to catch hallucinations,
invalid references, and malformed output.
"""
import os
import re
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def validate_affected_files(
    affected_files: Optional[List[str]],
    workspace_dir: str,
) -> Tuple[List[str], List[str]]:
    """
    Validate that affected files actually exist in the workspace.
    Returns (valid_files, hallucinated_files).
    """
    if not affected_files:
        return [], []

    valid = []
    hallucinated = []

    for f in affected_files:
        clean = f.lstrip('./')
        full_path = os.path.join(workspace_dir, clean)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            valid.append(clean)
        else:
            # Try basename search as a fallback
            basename = os.path.basename(clean)
            found = False
            for root, dirs, files in os.walk(workspace_dir):
                if basename in files:
                    found = True
                    break
            if not found:
                hallucinated.append(clean)
                logger.warning(f"Hallucinated file detected: {clean}")
            else:
                valid.append(clean)

    return valid, hallucinated


def validate_affected_functions(
    affected_functions: Optional[List[str]],
    affected_files: Optional[List[str]],
    workspace_dir: str,
) -> Tuple[List[str], List[str]]:
    """
    Validate that affected functions appear in the cited files.
    Returns (found_functions, not_found_functions).
    """
    if not affected_functions:
        return [], []
    if not affected_files:
        return [], list(affected_functions)

    found = []
    not_found = []

    for func_name in affected_functions:
        # Clean function name (remove parens, etc.)
        clean_func = func_name.strip().rstrip('()')
        if not clean_func:
            continue

        func_found = False
        for filepath in affected_files:
            clean_path = filepath.lstrip('./')
            full_path = os.path.join(workspace_dir, clean_path)
            if not os.path.exists(full_path):
                continue

            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Search for function/method definition patterns
                patterns = [
                    rf'\bdef\s+{re.escape(clean_func)}\b',      # Python
                    rf'\bfunction\s+{re.escape(clean_func)}\b',  # JS
                    rf'\b{re.escape(clean_func)}\s*[=(]',        # JS arrow/assignment
                    rf'\b{re.escape(clean_func)}\s*\(',          # General call/def
                ]
                for pattern in patterns:
                    if re.search(pattern, content):
                        func_found = True
                        break
                if func_found:
                    break
            except Exception:
                continue

        if func_found:
            found.append(func_name)
        else:
            not_found.append(func_name)
            logger.warning(f"Function not found in cited files: {func_name}")

    return found, not_found


def validate_confidence(confidence: Optional[float]) -> float:
    """Ensure confidence is between 0 and 1."""
    if confidence is None:
        return 0.5
    return max(0.0, min(1.0, confidence))


def classify_confidence(confidence: float) -> str:
    """Classify confidence level."""
    if confidence >= 0.80:
        return "HIGH"
    elif confidence >= 0.60:
        return "MEDIUM"
    else:
        return "LOW"


def contains_code_patch(text: Optional[str]) -> bool:
    """
    Detect if the diagnosis text contains an actual code patch/diff.
    The diagnosis agent should NOT produce patches.
    """
    if not text:
        return False

    patch_indicators = [
        r'^[+-]{3}\s+[ab]/',           # diff headers
        r'^@@\s.*@@',                   # diff hunks
        r'```diff',                     # markdown diff block
        r'PATCH:',                      # explicit patch label
        r'Replace\s+.*\s+with\s+.*:',  # replacement instructions
    ]

    for pattern in patch_indicators:
        if re.search(pattern, text, re.MULTILINE):
            return True

    return False


def validate_evidence(evidence: Optional[list]) -> list:
    """Validate evidence items have required fields."""
    if not evidence or not isinstance(evidence, list):
        return []

    valid_types = {"stack_trace", "test_failure", "source_location",
                   "reproduction_result", "configuration", "exception"}
    validated = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if "type" not in item or "description" not in item:
            continue
        # Normalize type
        if item["type"] not in valid_types:
            item["type"] = "source_location"
        validated.append(item)

    return validated


def compute_confidence_adjustment(
    hallucinated_files: List[str],
    not_found_functions: List[str],
    has_patch: bool,
    original_confidence: float,
) -> float:
    """
    Adjust confidence downward based on validation issues.
    """
    adjustment = original_confidence

    # Each hallucinated file drops confidence
    adjustment -= 0.15 * len(hallucinated_files)

    # Each missing function drops confidence slightly
    adjustment -= 0.05 * len(not_found_functions)

    # Patch presence is a warning but doesn't invalidate
    if has_patch:
        adjustment -= 0.1

    return max(0.0, min(1.0, adjustment))
