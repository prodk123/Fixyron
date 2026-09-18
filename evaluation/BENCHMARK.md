# FIXYRON BENCHMARK T1

**BUG:**
Division by zero raises `ZeroDivisionError` instead of `ValueError`.

**ROOT CAUSE:**
`divide()` does not explicitly handle a zero denominator.

**AFFECTED FILE:**
`calculator.py`

**AFFECTED FUNCTION:**
`divide()`

**EXPECTED FIX:**
Check whether `b == 0` before performing division and raise:
`ValueError("Cannot divide by zero")`

**EXPECTED TEST:**
`tests/test_calculator.py::test_divide_by_zero`

**EXPECTED RESULT AFTER FIX:**
All tests pass.
