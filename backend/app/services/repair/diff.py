import os
import subprocess

def get_git_diff(repo_path: str) -> str:
    """
    Returns the actual filesystem unified diff of all uncommitted changes.
    """
    try:
        # Check if it's a git repo
        result = subprocess.run(
            ["git", "status"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return "" # Not a git repository, or git failed
            
        # Get diff of modified files
        result = subprocess.run(
            ["git", "diff", "--unified=3"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        
        diff = result.stdout
        
        # Get diff of untracked files
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        
        for untracked_file in untracked.stdout.splitlines():
            file_path = os.path.join(repo_path, untracked_file)
            if os.path.isfile(file_path):
                # Fake a diff for untracked file
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                diff += f"\n--- /dev/null\n+++ b/{untracked_file}\n@@ -0,0 +1,{len(content.splitlines())} @@\n"
                for line in content.splitlines():
                    diff += f"+{line}\n"
                    
        return diff
    except Exception as e:
        print(f"Error getting git diff: {e}")
        return ""
