import os

def detect_language(repo_dir: str) -> tuple[str, int, int]:
    # Returns (primary_language, file_count, estimated_loc)
    
    lang_extensions = {
        "Python": {".py"},
        "JavaScript": {".js"},
        "TypeScript": {".ts", ".tsx"},
        "Java": {".java"},
        "C++": {".cpp", ".hpp", ".cc", ".cxx"},
        "Go": {".go"},
        "Rust": {".rs"}
    }
    
    scores = {lang: 0 for lang in lang_extensions}
    file_count = 0
    estimated_loc = 0
    
    ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "coverage", ".next"}
    
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            
            # Count language score
            for lang, exts in lang_extensions.items():
                if ext in exts:
                    scores[lang] += 1
                    break
            
            # Only count LOC for source files (approximate check)
            if ext in {".py", ".js", ".ts", ".tsx", ".java", ".cpp", ".hpp", ".go", ".rs"}:
                file_count += 1
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        estimated_loc += len([line for line in lines if line.strip()])
                except Exception:
                    # Ignore binary or non-utf8 files
                    pass

    # Find language with highest score
    primary_language = None
    if scores:
        best_lang = max(scores, key=scores.get)
        if scores[best_lang] > 0:
            primary_language = best_lang
            
    return primary_language, file_count, estimated_loc
