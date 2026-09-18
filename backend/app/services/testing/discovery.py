import os
import json
from typing import Optional

def detect_testing(repo_dir: str, primary_language: str) -> tuple[Optional[str], int]:
    framework = None
    test_file_count = 0
    
    test_patterns = []
    src_extensions = ()
    if primary_language == "Python":
        test_patterns = ["test_", "_test.py"]
        src_extensions = (".py",)
    elif primary_language in ("JavaScript", "TypeScript"):
        test_patterns = [".test.", ".spec.", "_test.", "-test."]
        src_extensions = (".js", ".jsx", ".ts", ".tsx")
    elif primary_language == "Java":
        test_patterns = ["test.java"]
        src_extensions = (".java",)
    elif primary_language == "Go":
        test_patterns = ["_test.go"]
        src_extensions = (".go",)
    elif primary_language == "Rust":
        src_extensions = (".rs",)

    ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "coverage"}

    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        is_test_dir = "test" in os.path.basename(root).lower() or "tests" in os.path.basename(root).lower()
        
        for file in files:
            file_lower = file.lower()
            
            is_test_file = any(pattern in file_lower for pattern in test_patterns)
            is_in_test_dir = is_test_dir and file_lower.endswith(src_extensions)
            
            if is_test_file or is_in_test_dir:
                test_file_count += 1
                
    # Detect testing framework
    if primary_language == "Python":
        for root, _, files in os.walk(repo_dir):
            for file in files:
                if file in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "tox.ini"):
                    try:
                        with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().lower()
                            if "pytest" in content:
                                framework = "pytest"
                                break
                            elif "unittest" in content and not framework:
                                framework = "unittest"
                    except Exception:
                        pass
            if framework == "pytest":
                break
    elif primary_language in ("JavaScript", "TypeScript"):
        for root, _, files in os.walk(repo_dir):
            if "package.json" in files:
                try:
                    with open(os.path.join(root, "package.json"), "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                        deps = {k.lower(): v for k, v in deps.items()}
                        
                        if "jest" in deps:
                            framework = "Jest"
                        elif "vitest" in deps:
                            framework = "Vitest"
                        elif "mocha" in deps:
                            framework = "Mocha"
                        elif "cypress" in deps:
                            framework = "Cypress"
                except Exception:
                    pass
    elif primary_language == "Java":
        for root, _, files in os.walk(repo_dir):
            if "pom.xml" in files or "build.gradle" in files:
                framework = "JUnit" # Simplification
                break
    elif primary_language == "Go":
        framework = "Go test"
    elif primary_language == "Rust":
        framework = "Cargo test"

    return framework, test_file_count
