# Task Board

Use this file as the single source of truth for active AI-agent work.

## Status Legend
- `todo`
- `in_progress`
- `review`
- `done`
- `blocked`

## Active Tasks

| ID | Title | Owner Agent | Status | Branch | Scope | Notes |
|---|---|---|---|---|---|---|
| T-001 | Example task | Codex | todo | `task/T-001-example` | `src/...`, `tests/...` | Replace with real task |

## Task Template

Copy this block for each new task:

```md
### T-XXX - <short title>
- Owner: Codex | Claude
- Status: todo | in_progress | review | done | blocked
- Branch: task/T-XXX-<slug>
- Goal:
  - <what done looks like>
- In scope:
  - <allowed files/modules>
- Out of scope:
  - <forbidden areas>
- Acceptance criteria:
  - [ ] behavior criteria 1
  - [ ] tests added/updated
  - [ ] `pytest -q` passes
  - [ ] docs updated if behavior changed
- Handoff notes:
  - <latest summary>
```

