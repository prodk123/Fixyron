# Week 4: Autonomous Fix Agent Architecture

## Overview
Week 4 introduces the `RepairAgent` capable of processing a diagnosed root cause and reproduction evidence to generate a structured candidate patch. It applies the proposed change into an isolated temporary workspace and runs the relevant reproduction test to determine if the candidate patch fixes the bug.

## Workflow
1. **Trigger**: A successful Reproduction and completed Diagnosis are required.
2. **Context Building**: The `build_repair_context` method assembles the bug description, stack trace, root cause, and actual source code context.
3. **Patch Generation**: The `RepairAgent` passes the context to the LLM and demands a structured JSON response (Pydantic `RepairOutput`).
4. **Validation**: The `patch_validator` enforces security and sanity boundaries (no `.env`, no `package.json`, limits file counts, limits line additions).
5. **Application**: The `workspace` module clones the baseline repository to a `/tmp/fixyron-repair-workspaces` directory and applies the patch.
6. **Testing**: The original Reproduction Test is executed via Docker within the temporary workspace.
7. **Persistence**: The actual generated diff and test results are saved to the `repairs` PostgreSQL table.

## Security Constraints
- **Original Repository Immutability**: All modifications happen strictly in the temporary repair workspace. The original baseline repository remains completely untouched.
- **Dependency Policy**: Modifications to `requirements.txt`, `package.json`, etc., are strictly blocked by the validator.
- **Path Traversal Protection**: Any path containing `../` or starting with `/` is rejected.
- **Untrusted Input**: The Agent prompt explicitly instructs the LLM to ignore any instructions embedded within source files (Prompt Injection defense).

## Database Schema
The `repairs` table includes:
- `status`: String tracking the progress (pending, generating, validating, applied, tested, completed, failed, error)
- `files_changed`, `lines_added`, `lines_removed`: Patch metadata
- `patch`: The actual Git diff generated after application
- `test_result`: JSON tracking stdout, stderr, and exit_code of the reproduction test.

## Week 5 Boundary
The Week 4 implementation intentionally stops after testing the generated patch. If the patch fails, the system logs the failure and does *not* automatically retry. The self-reflection and iterative re-planning loop is deferred to Week 5.
