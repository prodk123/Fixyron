import os
import json
from typing import Optional

def resolve_test_command(repo_dir: str, primary_language: str, framework: Optional[str]) -> str:
    if primary_language == "Python":
        # Usually pytest if detected, else python -m unittest
        if framework == "pytest":
            return "pytest"
        else:
            return "python -m unittest discover"

    elif primary_language in ("JavaScript", "TypeScript"):
        # Check package.json for "test" script
        pkg_path = os.path.join(repo_dir, "package.json")
        if os.path.exists(pkg_path):
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    if "test" in scripts and "echo" not in scripts["test"]:
                        return "npm test"
            except Exception:
                pass
        
        # Fallbacks based on framework
        if framework == "Jest":
            return "npx jest"
        elif framework == "Vitest":
            return "npx vitest run"
        elif framework == "Mocha":
            return "npx mocha"
        else:
            return "npm test"

    elif primary_language == "Java":
        if os.path.exists(os.path.join(repo_dir, "pom.xml")):
            return "mvn test"
        elif os.path.exists(os.path.join(repo_dir, "build.gradle")):
            return "./gradlew test"
        return "mvn test"

    elif primary_language == "Go":
        return "go test ./..."

    elif primary_language == "Rust":
        return "cargo test"

    # Default fallback
    return "make test"
