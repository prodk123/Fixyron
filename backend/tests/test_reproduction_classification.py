import pytest
from unittest.mock import patch, MagicMock
from app.services.qa.reproduction import perform_reproduction
from app.db.models.qa import ReproductionAttempt
from app.db.models.repository import RepositoryAnalysis

@pytest.fixture
def mock_db():
    db = MagicMock()
    analysis = RepositoryAnalysis(id="test_analysis", repository_url="http://test.repo", primary_language="Python", test_framework="pytest")
    attempt = ReproductionAttempt(id="test_attempt", analysis_id="test_analysis", bug_description="test bug")
    
    def mock_query(model):
        query = MagicMock()
        if model == RepositoryAnalysis:
            query.filter.return_value.first.return_value = analysis
        elif model == ReproductionAttempt:
            query.filter.return_value.first.return_value = attempt
        return query

    db.query.side_effect = mock_query
    return db

@patch("app.services.qa.reproduction.clone_repository")
@patch("app.services.qa.reproduction.generate_reproduction_test")
@patch("app.services.qa.reproduction.resolve_test_command")
@patch("app.services.qa.reproduction.run_tests_in_sandbox")
@patch("app.services.qa.reproduction.cleanup_workspace")
@patch("app.services.qa.reproduction.os.path.exists")
@patch("app.services.qa.reproduction.open")
def test_reproduction_classification(mock_open, mock_exists, mock_cleanup, mock_run, mock_resolve, mock_generate, mock_clone, mock_db):
    mock_clone.return_value = "/tmp/workspace"
    mock_exists.return_value = False
    mock_resolve.return_value = "pytest"
    mock_generate.return_value = {
        "test_framework": "pytest",
        "test_code": "def test_bug(): assert False",
        "target_files": [],
        "hypothesis": "Test",
        "confidence": 0.9,
        "test_file_path": "test_bug.py",
        "expected_behavior": "Should pass"
    }

    # Scenario 1: Successful test failure (non-zero exit code + tests_total > 0) -> REPRODUCED
    mock_run.return_value = {
        "status": "failed",
        "exit_code": 1,
        "tests_total": 1,
        "duration_ms": 100,
        "stdout": "AssertionError",
        "stderr": ""
    }
    attempt = perform_reproduction(mock_db, "test_analysis", "test_attempt", "test bug")
    assert attempt.classification == "reproduced"

    # Scenario 2: Successful test pass (0 exit code) -> NOT_REPRODUCED
    mock_run.return_value = {
        "status": "success",
        "exit_code": 0,
        "tests_total": 1,
        "duration_ms": 100,
        "stdout": "Passed",
        "stderr": ""
    }
    attempt = perform_reproduction(mock_db, "test_analysis", "test_attempt", "test bug")
    assert attempt.classification == "not_reproduced"

    # Scenario 3: Syntax error/crash (non-zero exit code + tests_total == 0) -> INCONCLUSIVE
    mock_run.return_value = {
        "status": "failed",
        "exit_code": 2,
        "tests_total": 0,
        "duration_ms": 100,
        "stdout": "SyntaxError",
        "stderr": ""
    }
    attempt = perform_reproduction(mock_db, "test_analysis", "test_attempt", "test bug")
    assert attempt.classification == "inconclusive"
    assert "Test infrastructure failed or test collection crashed" in attempt.evidence["reason"]

    # Scenario 4: Exception (e.g. LLM Timeout) -> INCONCLUSIVE
    mock_generate.side_effect = Exception("504 Gateway Timeout")
    attempt = perform_reproduction(mock_db, "test_analysis", "test_attempt", "test bug")
    assert attempt.classification == "inconclusive"
    assert attempt.evidence["status"] == "INCONCLUSIVE"
    assert attempt.evidence["error_type"] == "Exception"
    assert "504 Gateway Timeout" in attempt.evidence["reason"]
