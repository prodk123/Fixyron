import os

def analyze_structure(repo_dir: str) -> tuple[list[str], bool]:
    important_dirs = set()
    has_readme = False
    
    important_names = {"src", "app", "api", "backend", "frontend", "tests", "test", "docs", "config", "services", "components"}
    ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    
    # Just check top-level and one level down
    try:
        for item in os.listdir(repo_dir):
            item_path = os.path.join(repo_dir, item)
            
            if os.path.isfile(item_path) and item.lower().startswith("readme"):
                has_readme = True
                
            if os.path.isdir(item_path) and item not in ignore_dirs:
                if item.lower() in important_names:
                    important_dirs.add(item)
                
                # Check 1 level deep for src/app etc
                try:
                    for subitem in os.listdir(item_path):
                        if os.path.isdir(os.path.join(item_path, subitem)) and subitem.lower() in important_names:
                            important_dirs.add(f"{item}/{subitem}")
                except Exception:
                    pass
    except Exception:
        pass
        
    return list(important_dirs), has_readme

def find_relevant_files(repo_dir: str, bug_description: str) -> list[str]:
    if not bug_description:
        return []
        
    keywords = set(bug_description.lower().split())
    relevant = set()
    
    ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
    
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            file_lower = file.lower()
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, repo_dir).replace("\\", "/")
            
            # Simple heuristic matching
            for kw in keywords:
                if len(kw) > 3 and (kw in file_lower or kw in rel_path.lower()):
                    relevant.add(rel_path)
                    
    return list(relevant)[:10] # Return max 10 to avoid noise
