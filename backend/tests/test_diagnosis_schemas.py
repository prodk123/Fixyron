import pytest
from pydantic import ValidationError
from app.agents.diagnosis.schemas import DiagnosisOutput, EvidenceItem, AlternativeCause

def test_valid_diagnosis():
    data = {
        "summary": "Null pointer exception in auth service",
        "root_cause": "The user object is not checked for null before accessing the id property.",
        "affected_files": ["src/auth/service.js"],
        "affected_functions": ["authenticateUser"],
        "failure_mechanism": "When authenticateUser is called with an invalid token, it returns null, causing a TypeError when reading .id",
        "evidence": [
            {
                "type": "stack_trace",
                "file": "src/auth/service.js",
                "line": 42,
                "description": "TypeError: Cannot read property 'id' of null"
            }
        ],
        "confidence": 0.95,
        "alternative_causes": [
            {
                "description": "The token might be valid but the database is unreachable",
                "confidence": 0.1
            }
        ]
    }
    
    diagnosis = DiagnosisOutput(**data)
    assert diagnosis.summary == data["summary"]
    assert len(diagnosis.affected_files) == 1
    assert len(diagnosis.evidence) == 1

def test_missing_required_fields():
    data = {
        "summary": "Missing required fields"
        # root_cause is required but missing
    }
    
    with pytest.raises(ValidationError):
        DiagnosisOutput(**data)

def test_invalid_confidence_type():
    data = {
        "summary": "Valid summary",
        "root_cause": "Valid root cause",
        "affected_files": [],
        "affected_functions": [],
        "failure_mechanism": "Valid mechanism",
        "evidence": [],
        "confidence": "high", # Should be float
        "alternative_causes": []
    }
    
    with pytest.raises(ValidationError):
        DiagnosisOutput(**data)
