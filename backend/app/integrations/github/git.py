import os
import subprocess
import logging
from typing import Optional, List
from app.core.config import settings

logger = logging.getLogger(__name__)

class GitOperationsError(Exception):
    pass

class GitIntegration:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        
    def _run_git(self, args: List[str], env: Optional[dict] = None) -> str:
        cmd = ["git"] + args
        try:
            # We must be careful not to log URLs with tokens in them if we can help it, 
            # though subprocess might throw an error with it. We'll redact it manually if an error occurs.
            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                check=True,
                env=env or os.environ.copy()
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr or e.stdout
            # Redact token from error message if present
            if settings.GITHUB_TOKEN and settings.GITHUB_TOKEN in err_msg:
                err_msg = err_msg.replace(settings.GITHUB_TOKEN, "***REDACTED***")
            cmd_str = " ".join(cmd)
            if settings.GITHUB_TOKEN and settings.GITHUB_TOKEN in cmd_str:
                cmd_str = cmd_str.replace(settings.GITHUB_TOKEN, "***REDACTED***")
                
            logger.error(f"Git command failed: {cmd_str}\nError: {err_msg}")
            raise GitOperationsError(f"Git operation failed: {err_msg}")

    def clone(self, repo_url: str):
        # Insert token into clone url for auth
        if settings.GITHUB_TOKEN and repo_url.startswith("https://github.com/"):
            auth_url = repo_url.replace("https://github.com/", f"https://x-access-token:{settings.GITHUB_TOKEN}@github.com/")
        else:
            auth_url = repo_url
            
        # clone directly into the workspace path
        self._run_git(["clone", auth_url, "."])
        
        # set up fixyron user for commits
        self._run_git(["config", "user.name", "Fixyron"])
        self._run_git(["config", "user.email", "bot@fixyron.ai"])
        
    def create_branch(self, branch_name: str, base_sha: str):
        # Checkout the specific SHA
        self._run_git(["checkout", base_sha])
        # Create and checkout new branch
        self._run_git(["checkout", "-b", branch_name])
        
    def apply_patch(self, patch_path: str):
        # apply unified diff
        self._run_git(["apply", "--allow-empty", patch_path])
        
    def commit(self, message: str):
        self._run_git(["add", "-A"])
        self._run_git(["commit", "-m", message])
        
    def push(self, branch_name: str):
        self._run_git(["push", "origin", branch_name])
        
    def get_commit_sha(self) -> str:
        return self._run_git(["rev-parse", "HEAD"])
