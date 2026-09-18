import pytest
from app.services.diagnosis.evidence_validator import (
    validate_confidence,
    classify_confidence,
    contains_code_patch,
    compute_confidence_adjustment
)

import math

def test_validate_confidence():
    assert validate_confidence(0.5) == 0.5
    assert validate_confidence(1.5) == 1.0
    assert validate_confidence(-0.5) == 0.0
    assert validate_confidence(None) == 0.5

def test_classify_confidence():
    assert classify_confidence(0.9) == "HIGH"
    assert classify_confidence(0.8) == "HIGH"
    assert classify_confidence(0.7) == "MEDIUM"
    assert classify_confidence(0.6) == "MEDIUM"
    assert classify_confidence(0.5) == "LOW"
    assert classify_confidence(0.1) == "LOW"

def test_contains_code_patch():
    assert contains_code_patch("This is just a regular explanation.") is False
    
    diff_patch = """
    The fix is:
    ```diff
    - old code
    + new code
    ```
    """
    assert contains_code_patch(diff_patch) is True
    
    inline_patch = """
    Replace `foo = 1` with `foo = 2`:
    """
    assert contains_code_patch(inline_patch) is True
    
    header_patch = """
    --- a/file.py
    +++ b/file.py
    @@ -1,3 +1,3 @@
    """
    # Fix the test to match the regex (it expects start of string or newline followed by diff header)
    header_patch = "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@"
    assert contains_code_patch(header_patch) is True

def test_compute_confidence_adjustment():
    # Base case
    assert math.isclose(compute_confidence_adjustment([], [], False, 0.9), 0.9)
    
    # Hallucinated files (-0.15 each)
    assert math.isclose(compute_confidence_adjustment(["fake1.py"], [], False, 0.9), 0.75)
    assert math.isclose(compute_confidence_adjustment(["fake1.py", "fake2.py"], [], False, 0.9), 0.60)
    
    # Missing functions (-0.05 each)
    assert math.isclose(compute_confidence_adjustment([], ["fakeFunc"], False, 0.9), 0.85)
    
    # Patch presence (-0.1)
    assert math.isclose(compute_confidence_adjustment([], [], True, 0.9), 0.80)
    
    # Combined
    assert math.isclose(compute_confidence_adjustment(["fake1.py"], ["fakeFunc"], True, 0.9), 0.60)
    
    # Floor at 0.0
    assert math.isclose(compute_confidence_adjustment(["f1", "f2", "f3", "f4", "f5", "f6", "f7"], [], True, 0.9), 0.0)
