import os
import shutil
import subprocess
import uuid
import tempfile
from typing import List, Dict, Any, Tuple
from app.services.repository.clone import clone_repository
from app.services.repair.diff import get_git_diff

def create_repair_workspace(repo_url: str) -> str:
    """
    Creates a temporary workspace for the repair, completely isolated from
    the diagnosis and QA workspaces.
    Returns the absolute path to the workspace.
    """
    workspace_id = str(uuid.uuid4())
    # Use a specific repair workspace dir
    base_dir = "/tmp/fixyron-repair-workspaces"
    os.makedirs(base_dir, exist_ok=True)
    
    workspace_path = os.path.join(base_dir, workspace_id)
    
    # Clone the original repository into this isolated workspace
    # This guarantees the baseline is clean and the original repo is untouched.
    clone_repository(repo_url, workspace_path)
    
    return workspace_path

def apply_patch_to_workspace(workspace_path: str, files_changed: List[Any]) -> None:
    """
    Safely applies the parsed FilePatch list to the workspace.
    """
    for fp in files_changed:
        file_path = os.path.join(workspace_path, fp.path)
        
        if fp.operation == "create":
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fp.patch)
        elif fp.operation == "modify":
            # Use 'patch' utility to apply unified diff
            # Write diff to temporary file
            with tempfile.NamedTemporaryFile("w", delete=False) as tf:
                tf.write(fp.patch)
                diff_path = tf.name
                
            try:
                # -p1 is typical, but LLM diffs might not have a/ and b/ prefixes properly.
                # Let's try standard patch command.
                # If it fails, fallback to python diff-match-patch or similar if needed.
                # For Week 4, we use strict deterministic patch.
                result = subprocess.run(
                    ["patch", "-p1", "--no-backup-if-mismatch"],
                    cwd=workspace_path,
                    input=fp.patch,
                    text=True,
                    capture_output=True
                )
                
                if result.returncode != 0:
                    # Retry with -p0 if -p1 fails
                    result_p0 = subprocess.run(
                        ["patch", "-p0", "--no-backup-if-mismatch"],
                        cwd=workspace_path,
                        input=fp.patch,
                        text=True,
                        capture_output=True
                    )
                    if result_p0.returncode != 0:
                        raise ValueError(f"Failed to apply patch to {fp.path}: {result.stderr}\n{result_p0.stderr}")
            finally:
                os.unlink(diff_path)
        else:
            raise ValueError(f"Unsupported operation: {fp.operation}")

def cleanup_repair_workspace(workspace_path: str) -> None:
    """
    Deletes the temporary repair workspace.
    """
    if workspace_path and os.path.exists(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=True)
