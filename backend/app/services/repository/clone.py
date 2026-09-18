import os
import shutil
import subprocess
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Base path for temporary workspaces
# Mapped via docker-compose to /tmp/fixyron-workspaces
WORKSPACE_BASE = "/tmp/fixyron-workspaces"

def setup_workspaces():
    os.makedirs(WORKSPACE_BASE, exist_ok=True)

def clone_repository(repo_url: str, target_dir: str = None) -> Optional[str]:
    setup_workspaces()
    
    if target_dir:
        repo_dir = target_dir
        os.makedirs(os.path.dirname(repo_dir), exist_ok=True)
    else:
        workspace_id = str(uuid.uuid4())
        repo_dir = os.path.join(WORKSPACE_BASE, workspace_id)
    
    try:
        # Use subprocess argument array for safety. Avoid shell=True.
        # Ensure url does not contain malicious parts.
        logger.info(f"Cloning {repo_url} into {repo_dir}")
        process = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_dir],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout for clone
        )
        
        if process.returncode != 0:
            logger.error(f"Clone failed: {process.stderr}")
            return None
            
        return repo_dir
    except subprocess.TimeoutExpired:
        logger.error(f"Clone timed out for {repo_url}")
        return None
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        return None

def cleanup_workspace(repo_dir: str):
    try:
        if os.path.exists(repo_dir) and repo_dir.startswith(WORKSPACE_BASE):
            shutil.rmtree(repo_dir)
            logger.info(f"Cleaned up workspace {repo_dir}")
    except Exception as e:
        logger.error(f"Failed to cleanup workspace {repo_dir}: {e}")
