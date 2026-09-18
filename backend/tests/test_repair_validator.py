import pytest
from app.services.repair.patch_validator import validate_patch
from app.agents.repair.schemas import RepairOutput, FilePatch

def test_validate_patch_empty():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[]
    )
    with pytest.raises(ValueError, match="Patch is empty"):
        validate_patch(repair_output, [])

def test_validate_patch_path_traversal():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[
            FilePatch(path="../secrets.txt", operation="modify", patch="test")
        ]
    )
    with pytest.raises(ValueError, match="Path traversal or absolute path detected"):
        validate_patch(repair_output, [])

def test_validate_patch_absolute_path():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[
            FilePatch(path="/etc/passwd", operation="modify", patch="test")
        ]
    )
    with pytest.raises(ValueError, match="Path traversal or absolute path detected"):
        validate_patch(repair_output, [])

def test_validate_patch_protected_file():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[
            FilePatch(path=".git/config", operation="modify", patch="test")
        ]
    )
    with pytest.raises(ValueError, match="Attempted to modify protected path"):
        validate_patch(repair_output, [])

def test_validate_patch_dependency():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[
            FilePatch(path="package.json", operation="modify", patch="test")
        ]
    )
    with pytest.raises(ValueError, match="Dependency modification is not allowed"):
        validate_patch(repair_output, [])

def test_validate_patch_test_file_without_diagnosis():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[
            FilePatch(path="tests/test_auth.py", operation="modify", patch="test")
        ]
    )
    with pytest.raises(ValueError, match="Modification of test files is blocked by default"):
        validate_patch(repair_output, ["src/auth.py"])

def test_validate_patch_success():
    repair_output = RepairOutput(
        summary="Test",
        reasoning_summary="Test",
        expected_effect="Test",
        confidence=0.9,
        files_changed=[
            FilePatch(path="src/auth.py", operation="modify", patch="test")
        ]
    )
    assert validate_patch(repair_output, ["src/auth.py"]) is None
