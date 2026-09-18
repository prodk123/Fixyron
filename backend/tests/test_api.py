import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fixyron-backend"}

def test_analyze_repository_invalid_url():
    response = client.post(
        "/api/repositories/analyze",
        json={"repository_url": "http://invalid-url.com"}
    )
    assert response.status_code == 400 # Custom validation

def test_analyze_repository_invalid_github():
    response = client.post(
        "/api/repositories/analyze",
        json={"repository_url": "https://github.com/invalid"}
    )
    assert response.status_code == 400
    assert "Invalid GitHub" in response.json()["detail"]
