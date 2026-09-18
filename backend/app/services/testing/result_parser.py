import re
from typing import Dict, Any

def parse_test_results(stdout: str, stderr: str, framework: str) -> Dict[str, Any]:
    # Combine outputs for parsing
    output = stdout + "\n" + stderr
    
    results = {
        "tests_total": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
    }
    
    if not output:
        return results
        
    # Pytest parser
    # Example: = 2 failed, 1 passed, 1 skipped, 1 warning, 1 error in 0.42s =
    if framework == "pytest":
        # Check for pytest summary line
        match = re.search(r'==.*?(\d+ passed|\d+ failed|\d+ skipped|\d+ error).*?==', output, re.IGNORECASE)
        if not match:
            # Try finding it without ==
            lines = output.splitlines()
            for line in reversed(lines):
                if "passed" in line or "failed" in line or "skipped" in line:
                    match = re.search(r'(\d+ passed|\d+ failed|\d+ skipped|\d+ error)', line)
                    if match:
                        summary_line = line
                        break
            else:
                summary_line = ""
        else:
            summary_line = match.group(0)
            
        if summary_line:
            passed = re.search(r'(\d+) passed', summary_line)
            failed = re.search(r'(\d+) failed', summary_line)
            skipped = re.search(r'(\d+) skipped', summary_line)
            errors = re.search(r'(\d+) error', summary_line)
            
            results["tests_passed"] = int(passed.group(1)) if passed else 0
            
            fail_count = int(failed.group(1)) if failed else 0
            err_count = int(errors.group(1)) if errors else 0
            results["tests_failed"] = fail_count + err_count
            
            results["tests_skipped"] = int(skipped.group(1)) if skipped else 0
            results["tests_total"] = results["tests_passed"] + results["tests_failed"] + results["tests_skipped"]

    # Jest / Vitest parser
    # Example: Tests:       2 failed, 10 passed, 12 total
    elif framework in ("Jest", "Vitest"):
        tests_line_match = re.search(r'Tests:\s+(.*?total)', output)
        if tests_line_match:
            tests_line = tests_line_match.group(1)
            passed = re.search(r'(\d+) passed', tests_line)
            failed = re.search(r'(\d+) failed', tests_line)
            skipped = re.search(r'(\d+) skipped', tests_line)
            total = re.search(r'(\d+) total', tests_line)
            
            results["tests_passed"] = int(passed.group(1)) if passed else 0
            results["tests_failed"] = int(failed.group(1)) if failed else 0
            results["tests_skipped"] = int(skipped.group(1)) if skipped else 0
            results["tests_total"] = int(total.group(1)) if total else (results["tests_passed"] + results["tests_failed"] + results["tests_skipped"])
            
    # Mocha parser
    # Example: 10 passing (12ms)\n  2 failing
    elif framework == "Mocha":
        passed = re.search(r'(\d+)\s+passing', output)
        failed = re.search(r'(\d+)\s+failing', output)
        
        results["tests_passed"] = int(passed.group(1)) if passed else 0
        results["tests_failed"] = int(failed.group(1)) if failed else 0
        results["tests_total"] = results["tests_passed"] + results["tests_failed"]

    return results
