"""
Focused code retrieval system for diagnosis context.
Ranks candidate files by relevance and extracts targeted code regions.
"""
import os
import re
import logging
from typing import List, Dict, Optional, Set
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Files/directories to always exclude from code retrieval
EXCLUDED_PATTERNS = {
    '.env', '.git', '__pycache__', 'node_modules', '.next',
    'venv', '.venv', 'dist', 'build', '.tox', '.mypy_cache',
    '.pytest_cache', 'egg-info', '.eggs',
}

# File extensions that are binary or irrelevant
EXCLUDED_EXTENSIONS = {
    '.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe', '.bin',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff',
    '.woff2', '.ttf', '.eot', '.mp3', '.mp4', '.zip', '.tar',
    '.gz', '.pdf', '.lock',
}

# Sensitive files to never include in LLM context
SENSITIVE_PATTERNS = {
    '.env', '.env.local', '.env.production', '.env.development',
    'secrets', 'credentials', 'private_key', 'id_rsa',
    '.pem', '.key', '.crt', '.p12',
}


class CodeContext(BaseModel):
    file: str
    start_line: int
    end_line: int
    content: str
    score: float
    reason: str


class RankedFile(BaseModel):
    path: str
    score: float
    reason: str


def is_excluded(filepath: str) -> bool:
    """Check if a file should be excluded from code retrieval."""
    basename = os.path.basename(filepath).lower()
    _, ext = os.path.splitext(filepath)

    # Check sensitive patterns
    for pattern in SENSITIVE_PATTERNS:
        if pattern in basename:
            return True

    # Check excluded extensions
    if ext.lower() in EXCLUDED_EXTENSIONS:
        return True

    # Check excluded directory patterns
    parts = filepath.replace('\\', '/').split('/')
    for part in parts:
        if part in EXCLUDED_PATTERNS:
            return True

    return False


def rank_files(
    workspace_dir: str,
    stack_trace_files: List[str],
    reproduction_target_files: Optional[List[str]],
    relevant_files: Optional[List[str]],
    bug_description: str,
    max_files: int = 10,
) -> List[RankedFile]:
    """
    Rank candidate files by relevance to the bug.
    Priority order:
    1. Files appearing in stack traces (highest)
    2. Reproduction test target files
    3. Heuristic relevant files from Week 1 analysis
    4. Files matching bug description keywords
    """
    file_scores: Dict[str, Dict] = {}

    def add_score(path: str, score: float, reason: str):
        # Normalize path
        clean = path.lstrip('./')
        if clean in file_scores:
            file_scores[clean]["score"] += score
            file_scores[clean]["reasons"].append(reason)
        else:
            file_scores[clean] = {"score": score, "reasons": [reason]}

    # 1. Stack trace files get highest priority
    for f in stack_trace_files:
        # Try to resolve relative to workspace
        clean = f.lstrip('./')
        if os.path.exists(os.path.join(workspace_dir, clean)):
            add_score(clean, 0.5, "Appears in stack trace")
        else:
            # Try basename match
            basename = os.path.basename(f)
            for root, dirs, files in os.walk(workspace_dir):
                for fname in files:
                    if fname == basename:
                        rel = os.path.relpath(os.path.join(root, fname), workspace_dir).replace('\\', '/')
                        add_score(rel, 0.4, f"Stack trace basename match ({basename})")

    # 2. Reproduction target files
    if reproduction_target_files:
        for f in reproduction_target_files:
            clean = f.lstrip('./')
            if os.path.exists(os.path.join(workspace_dir, clean)):
                add_score(clean, 0.3, "Reproduction test target")

    # 3. Week 1 relevant files
    if relevant_files:
        for f in relevant_files:
            clean = f.lstrip('./')
            if os.path.exists(os.path.join(workspace_dir, clean)):
                add_score(clean, 0.15, "Heuristic relevance analysis")

    # 4. Keyword matching from bug description
    if bug_description:
        keywords = extract_keywords(bug_description)
        if keywords:
            for root, dirs, files in os.walk(workspace_dir):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in EXCLUDED_PATTERNS]
                for fname in files:
                    rel = os.path.relpath(os.path.join(root, fname), workspace_dir).replace('\\', '/')
                    if is_excluded(rel):
                        continue
                    name_lower = fname.lower()
                    for kw in keywords:
                        if kw in name_lower:
                            add_score(rel, 0.1, f"Filename matches keyword '{kw}'")
                            break

    # Filter excluded files and sort
    ranked = []
    for path, data in file_scores.items():
        if is_excluded(path):
            continue
        if not os.path.exists(os.path.join(workspace_dir, path)):
            continue
        ranked.append(RankedFile(
            path=path,
            score=min(data["score"], 1.0),
            reason="; ".join(data["reasons"])
        ))

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:max_files]


def extract_keywords(bug_description: str) -> List[str]:
    """Extract meaningful keywords from a bug description."""
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'is', 'was', 'are', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'can', 'shall',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'it', 'this', 'that', 'which', 'when', 'where', 'how', 'what',
        'who', 'whom', 'and', 'or', 'but', 'not', 'no', 'if', 'then',
        'so', 'because', 'as', 'than', 'too', 'very', 'just', 'about',
        'bug', 'error', 'issue', 'problem', 'fix', 'broken', 'fails',
        'instead', 'returns', 'should', 'expected', 'actual',
    }

    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', bug_description.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    return list(set(keywords))


def extract_code_context(
    workspace_dir: str,
    filepath: str,
    target_lines: Optional[List[int]] = None,
    context_lines: int = 15,
    max_chars: int = 3000,
) -> Optional[CodeContext]:
    """
    Extract a focused code region from a file.
    If target_lines are provided, extracts around those lines.
    Otherwise extracts the most relevant portion (imports + first functions).
    """
    full_path = os.path.join(workspace_dir, filepath)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return None

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return None

    if not lines:
        return None

    total_lines = len(lines)

    if target_lines:
        # Extract around the target lines
        min_line = max(1, min(target_lines) - context_lines)
        max_line = min(total_lines, max(target_lines) + context_lines)
    else:
        # Extract the first meaningful portion
        min_line = 1
        max_line = min(total_lines, 80)

    content = ''.join(lines[min_line - 1:max_line])

    # Truncate if too large
    if len(content) > max_chars:
        content = content[:max_chars] + "\n... (truncated)"

    return CodeContext(
        file=filepath,
        start_line=min_line,
        end_line=max_line,
        content=content,
        score=0.0,  # Will be set by caller
        reason=""    # Will be set by caller
    )


def retrieve_code_contexts(
    workspace_dir: str,
    ranked_files: List[RankedFile],
    stack_trace_lines: Optional[Dict[str, List[int]]] = None,
    max_total_chars: int = 15000,
) -> List[CodeContext]:
    """
    Retrieve focused code contexts from ranked files.
    Respects a total character budget to avoid overwhelming LLM context.
    """
    contexts = []
    total_chars = 0

    for rf in ranked_files:
        if total_chars >= max_total_chars:
            break

        # Determine target lines from stack trace
        target_lines = None
        if stack_trace_lines and rf.path in stack_trace_lines:
            target_lines = stack_trace_lines[rf.path]

        remaining_budget = max_total_chars - total_chars
        ctx = extract_code_context(
            workspace_dir, rf.path,
            target_lines=target_lines,
            max_chars=min(3000, remaining_budget)
        )

        if ctx:
            ctx.score = rf.score
            ctx.reason = rf.reason
            contexts.append(ctx)
            total_chars += len(ctx.content)

    return contexts
