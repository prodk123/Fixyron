from typing import List, Dict, Any

def validate_patch(repair_output: Any, diagnosis_affected_files: List[str]) -> None:
    """
    Validates the patch for safety limits and boundaries.
    Raises ValueError if validation fails.
    """
    if not repair_output.files_changed:
        raise ValueError("Patch is empty: No files changed.")
        
    MAX_PATCH_FILES = 5
    MAX_PATCH_LINES = 200
    
    if len(repair_output.files_changed) > MAX_PATCH_FILES:
        raise ValueError(f"Patch exceeds limit: modified {len(repair_output.files_changed)} files (max {MAX_PATCH_FILES}).")
        
    for fp in repair_output.files_changed:
        path = fp.path
        
        if "../" in path or path.startswith("/"):
            raise ValueError(f"Path traversal or absolute path detected: {path}")
            
        protected_prefixes = [".git/", ".env", "secrets/", "credentials/"]
        for p in protected_prefixes:
            if path.startswith(p) or p in path:
                raise ValueError(f"Attempted to modify protected path: {path}")
                
        dependency_files = [
            "requirements.txt", "pyproject.toml", "Pipfile", 
            "package.json", "package-lock.json", "yarn.lock", 
            "pnpm-lock.yaml", "poetry.lock", "pom.xml", 
            "build.gradle", "go.mod", "Cargo.toml"
        ]
        
        if any(path.endswith(df) for df in dependency_files):
            raise ValueError(f"Dependency modification is not allowed in Week 4: {path}")
            
        if "test" in path.lower() and not (diagnosis_affected_files and path in diagnosis_affected_files):
            raise ValueError(f"Modification of test files is blocked by default unless explicitly identified in diagnosis: {path}")

        # Check line limit on patch
        lines = fp.patch.split("\n")
        added_lines = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
        
        if added_lines > MAX_PATCH_LINES:
            raise ValueError(f"Patch too large: {added_lines} lines added in {path} (max {MAX_PATCH_LINES}).")
            
    # Success
    return None
