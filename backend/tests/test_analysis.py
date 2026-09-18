from app.services.repository.validation import validate_github_url
import pytest
from fastapi import HTTPException
from pydantic import HttpUrl

def test_validate_github_url_valid():
    url = HttpUrl("https://github.com/owner/repo")
    assert validate_github_url(url) == "https://github.com/owner/repo"

def test_validate_github_url_valid_with_git():
    url = HttpUrl("https://github.com/owner/repo.git")
    assert validate_github_url(url) == "https://github.com/owner/repo"

def test_validate_github_url_invalid_domain():
    url = HttpUrl("https://gitlab.com/owner/repo")
    with pytest.raises(HTTPException):
        validate_github_url(url)
