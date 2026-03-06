# Dev Team Playbook (Codex + Claude)

## Goal
Use multiple AI agents safely and predictably without branch conflicts or unclear ownership.

## Agent Roles

### Codex (Implementer)
- Primary owner for code changes.
- Default scope:
  - `src/db/*`
  - `src/runtime/*`
  - `src/services/*`
  - wiring in `src/discord_bot.py`
- Responsible for:
  - implementation
  - refactors
  - tests for changed behavior
  - migration/query correctness

### Claude (Reviewer + Product/Docs)
- Primary owner for review quality and behavior clarity.
- Default scope:
  - PR review on all changes
  - `src/commands/*`
  - `src/discord_text.py`
  - `README.md`, `ARCHITECTURE.md`, `OPERATIONS.md`
- Responsible for:
  - findings-first review (bugs/regressions/test gaps)
  - command UX and channel-policy consistency
  - docs sync with shipped behavior

## Operating Rules
- Never push directly to `main`.
- One branch per task, one agent writing on that branch at a time.
- Keep PRs small and scoped to one subsystem when possible.
- Use commit format: `type(scope): summary`.
- Required before merge:
  - `pytest -q` passes
  - no unresolved high-severity review findings
  - docs updated when behavior changes

## Standard Workflow
1. Create/update task in `TASKS.md`.
2. Assign owner agent.
3. Codex implements and opens PR.
4. Claude reviews with severity (`High/Medium/Low`) and required fixes.
5. Codex applies fixes and updates tests/docs.
6. Merge after CI + review gates pass.

## PR Template
Use this structure in every PR description:

```md
## Purpose
- What this changes and why.

## Scope
- Files/modules touched.
- Explicitly out-of-scope items.

## Tests
- Commands run and outcomes.

## Risks
- Behavioral or operational risks.
- Rollback plan (if needed).

## Docs/Runbook
- Which docs were updated (or why not needed).
```

## Handoff Template
Use this when handing work from one agent to another:

```md
### Handoff
- Task ID:
- Branch:
- Changes made:
- Tests run:
- Open risks/questions:
- Next expected action:
```

## Review Template (Findings First)
Claude should review using:

```md
### Findings
1. [High|Medium|Low] <issue summary> - <file:line>

### Open Questions
1. <question>

### Residual Risk
- <remaining risk after fixes>
```

## Suggested Routing
- DB/migrations/query correctness: Codex -> Claude review
- Worker/runtime reliability: Codex -> Claude review
- Command behavior/help text/docs: Codex implementation, Claude signs off on UX/docs

