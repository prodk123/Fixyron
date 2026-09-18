# Week 1 Architecture

## System Architecture

```text
Next.js
   ↓
FastAPI
   ↓
Repository Service
   ↓
Analysis Engine
   ↓
PostgreSQL
```

## Request Lifecycle
1. User enters a GitHub URL and optional bug description on the Next.js frontend.
2. The frontend sends a `POST /api/repositories/analyze` request to the FastAPI backend.
3. The backend validates the URL (preventing malicious inputs or unauthorized protocols).
4. A unique, temporary workspace is created.
5. The repository is cloned into the temporary workspace safely using a subprocess without shell execution.
6. The analysis engine heuristically detects the project language, framework, testing framework, LOC, and relevant files.
7. The structured result is persisted in PostgreSQL.
8. The frontend polls or retrieves the result via `GET /api/repositories/{analysis_id}` and displays it to the user.

## Security Model
- **Repository Validation**: Only `https://github.com/` URLs are permitted.
- **No Code Execution**: During Week 1, the repository is only statically analyzed. No code, tests, or scripts from the repository are executed.
- **Subprocess Safety**: Shell execution is avoided. `git clone` uses argument arrays to prevent command injection.
- **Isolation**: Repositories are cloned into temporary `/tmp` workspaces, isolating them from the main codebase.

## Future Evolution
This foundation establishes a clean separation between the API, Services, and Analysis Engine. In later weeks, the Analysis Engine will feed its structured output into LangGraph workflows. The multi-agent repair pipeline will use this deterministic context to initialize AI agents (Repository Agent, Bug Analyst, Fix Agent) for autonomous QA and bug fixing.
