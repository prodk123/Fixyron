"""
Stack trace parser for Python and JavaScript/Node.js tracebacks.
Extracts file paths, line numbers, function names, exception type, and message.
"""
import re
import logging
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class StackFrame(BaseModel):
    file: str
    line: Optional[int] = None
    function: Optional[str] = None


class ParsedStackTrace(BaseModel):
    exception_type: Optional[str] = None
    message: Optional[str] = None
    frames: List[StackFrame] = []


def parse_python_traceback(text: str) -> Optional[ParsedStackTrace]:
    """
    Parse a Python traceback from raw text.
    Example:
        Traceback (most recent call last):
          File "app/service.py", line 57, in get_user
            return users[user_id]
        KeyError: 'user_id'
    """
    # Find the traceback block
    tb_match = re.search(r'Traceback \(most recent call last\):(.*?)(\w+Error|\w+Exception|\w+Warning|KeyError|ValueError|TypeError|AttributeError|ImportError|RuntimeError|StopIteration|OSError|FileNotFoundError|PermissionError|IndexError|NameError|ZeroDivisionError|AssertionError|NotImplementedError|Exception):\s*(.*?)$',
                         text, re.DOTALL | re.MULTILINE)

    if not tb_match:
        # Try a simpler pattern: just look for exception at end
        simple_match = re.search(r'(\w+(?:Error|Exception)):\s*(.+?)$', text, re.MULTILINE)
        if simple_match:
            return ParsedStackTrace(
                exception_type=simple_match.group(1),
                message=simple_match.group(2).strip(),
                frames=[]
            )
        return None

    tb_body = tb_match.group(1)
    exception_type = tb_match.group(2)
    exception_message = tb_match.group(3).strip()

    # Extract frames: File "path", line N, in func_name
    frame_pattern = re.compile(
        r'File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+(\S+))?'
    )

    frames = []
    for match in frame_pattern.finditer(tb_body):
        filepath = match.group(1)
        line_num = int(match.group(2))
        func_name = match.group(3) if match.group(3) else None

        # Skip internal Python/pip/site-packages frames
        if any(skip in filepath for skip in ['site-packages', '/usr/lib/python', '<frozen']):
            continue

        frames.append(StackFrame(
            file=filepath,
            line=line_num,
            function=func_name
        ))

    return ParsedStackTrace(
        exception_type=exception_type,
        message=exception_message,
        frames=frames
    )


def parse_javascript_traceback(text: str) -> Optional[ParsedStackTrace]:
    """
    Parse a JavaScript/Node.js stack trace.
    Example:
        TypeError: Cannot read properties of undefined (reading 'id')
            at getUser (/app/src/service.js:42:15)
            at handler (/app/src/routes.js:18:10)
    """
    # Match the error line
    error_match = re.search(r'^(\w+(?:Error|Exception|TypeError|RangeError|ReferenceError|SyntaxError|URIError)):\s*(.+?)$',
                            text, re.MULTILINE)

    if not error_match:
        return None

    exception_type = error_match.group(1)
    exception_message = error_match.group(2).strip()

    # Extract frames: at funcName (filepath:line:col) or at filepath:line:col
    frame_pattern = re.compile(
        r'at\s+(?:(\S+)\s+)?\(?([^:]+):(\d+)(?::(\d+))?\)?'
    )

    frames = []
    for match in frame_pattern.finditer(text):
        func_name = match.group(1) if match.group(1) else None
        filepath = match.group(2)
        line_num = int(match.group(3))

        # Skip node internals
        if any(skip in filepath for skip in ['node_modules', 'node:internal', '<anonymous>']):
            continue

        frames.append(StackFrame(
            file=filepath,
            line=line_num,
            function=func_name
        ))

    if not frames:
        return None

    return ParsedStackTrace(
        exception_type=exception_type,
        message=exception_message,
        frames=frames
    )


def parse_stack_trace(text: str, language: str = "Python") -> Optional[ParsedStackTrace]:
    """
    Parse a stack trace from raw text, dispatching to the appropriate language parser.
    """
    if not text:
        return None

    if language in ("JavaScript", "TypeScript"):
        return parse_javascript_traceback(text)
    else:
        # Default to Python
        return parse_python_traceback(text)
