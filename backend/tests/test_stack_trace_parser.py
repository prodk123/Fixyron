import pytest
from app.services.diagnosis.stack_trace_parser import parse_python_traceback, parse_javascript_traceback, parse_stack_trace

PYTHON_TRACEBACK = """
Traceback (most recent call last):
  File "app/main.py", line 10, in <module>
    result = compute_value(x)
  File "app/utils.py", line 42, in compute_value
    return data['value']
KeyError: 'value'
"""

JS_TRACEBACK = """
TypeError: Cannot read properties of undefined (reading 'id')
    at getUser (/app/src/service.js:42:15)
    at handler (/app/src/routes.js:18:10)
    at Object.module.exports [as callback] (/app/node_modules/express/lib/router/index.js:50:10)
"""

def test_parse_python_traceback():
    result = parse_python_traceback(PYTHON_TRACEBACK)
    assert result is not None
    assert result.exception_type == "KeyError"
    assert result.message == "'value'"
    assert len(result.frames) == 2
    
    assert result.frames[0].file == "app/main.py"
    assert result.frames[0].line == 10
    assert result.frames[0].function == "<module>"
    
    assert result.frames[1].file == "app/utils.py"
    assert result.frames[1].line == 42
    assert result.frames[1].function == "compute_value"

def test_parse_javascript_traceback():
    result = parse_javascript_traceback(JS_TRACEBACK)
    assert result is not None
    assert result.exception_type == "TypeError"
    assert result.message == "Cannot read properties of undefined (reading 'id')"
    # Should exclude node_modules frame
    assert len(result.frames) == 2
    
    assert result.frames[0].file == "/app/src/service.js"
    assert result.frames[0].line == 42
    assert result.frames[0].function == "getUser"
    
    assert result.frames[1].file == "/app/src/routes.js"
    assert result.frames[1].line == 18
    assert result.frames[1].function == "handler"

def test_parse_stack_trace_dispatch():
    py_result = parse_stack_trace(PYTHON_TRACEBACK, "Python")
    assert py_result.exception_type == "KeyError"
    
    js_result = parse_stack_trace(JS_TRACEBACK, "JavaScript")
    assert js_result.exception_type == "TypeError"
