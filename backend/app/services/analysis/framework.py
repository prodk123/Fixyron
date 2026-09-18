import os
import json
from typing import Optional

def detect_framework(repo_dir: str, primary_language: str) -> Optional[str]:
    framework = None
    
    # Python frameworks
    if primary_language == "Python":
        # Check requirements.txt, pyproject.toml, Pipfile
        for root, _, files in os.walk(repo_dir):
            if "requirements.txt" in files:
                with open(os.path.join(root, "requirements.txt"), "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    if "fastapi" in content:
                        return "FastAPI"
                    if "django" in content:
                        return "Django"
                    if "flask" in content:
                        return "Flask"
            if "pyproject.toml" in files:
                with open(os.path.join(root, "pyproject.toml"), "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    if "fastapi" in content:
                        return "FastAPI"
                    if "django" in content:
                        return "Django"
                    if "flask" in content:
                        return "Flask"
                        
    # JS/TS frameworks
    elif primary_language in ("JavaScript", "TypeScript"):
        for root, _, files in os.walk(repo_dir):
            if "package.json" in files:
                try:
                    with open(os.path.join(root, "package.json"), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                        deps = {k.lower(): v for k, v in deps.items()}
                        
                        if "next" in deps:
                            return "Next.js"
                        if "react" in deps:
                            return "React"
                        if "express" in deps:
                            return "Express"
                        if "@nestjs/core" in deps:
                            return "NestJS"
                        if "vue" in deps:
                            return "Vue"
                        if "@angular/core" in deps:
                            return "Angular"
                except Exception:
                    pass
    
    return framework
