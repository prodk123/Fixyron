import httpx
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.base_url = "https://api.github.com"
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            with httpx.Client() as client:
                response = client.request(method, url, headers=self.headers, timeout=30.0, **kwargs)
                response.raise_for_status()
                if response.status_code == 204:
                    return {}
                return response.json()
        except httpx.HTTPStatusError as e:
            # We must be careful not to log the auth token in error messages
            logger.error(f"GitHub API Error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API request failed with status {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"GitHub Network Error: {str(e)}")
            raise Exception(f"GitHub Network Error: {str(e)}")

    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        return self._request("GET", f"/repos/{owner}/{repo}")

    def get_branch(self, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        return self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")
        
    def check_branch_exists(self, owner: str, repo: str, branch: str) -> bool:
        try:
            self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")
            return True
        except Exception:
            return False

    def create_pull_request(self, owner: str, repo: str, title: str, body: str, head: str, base: str) -> Dict[str, Any]:
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        return self._request("POST", f"/repos/{owner}/{repo}/pulls", json=payload)
    
    def check_pull_request_exists(self, owner: str, repo: str, head: str, base: str) -> Optional[Dict[str, Any]]:
        # Fetch PRs to see if one exists for the given head
        try:
            prs = self._request("GET", f"/repos/{owner}/{repo}/pulls?head={owner}:{head}&base={base}&state=all")
            if prs and len(prs) > 0:
                return prs[0]
            return None
        except Exception as e:
            logger.error(f"Failed to check PR existence: {e}")
            return None
