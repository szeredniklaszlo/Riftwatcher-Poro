# Improvement Backlog

This backlog tracks work not yet implemented as of 2026-02-25.

## Source docs reviewed

- `SESSION_NOTES.md`
- `README.md`
- `ARCHITECTURE.md`
- `OPERATIONS.md`

## Operational Improvements

1. Add lightweight metrics export for worker cycle latency and error rates
- Current gap: cycle timings are logged, but there is no persistent metrics sink/dashboard.

2. Add alerting for stalled workers
- Current gap: worker cycles/errors are visible via `!health`, but no proactive alert when a worker stops progressing.

## Scoring V2 (Draft)

3. Implement Gamer Score v2 composite model
- Candidate components:
  - Bayesian smoothing for win rate (`p_bayes`)
  - Confidence/volume weighting (`conf`)
  - role-aware normalized performance (`perf_norm`)
  - recency weighting (`recency_norm`)
- Current gap: production score is still Wilson-based.

## Feature Backlog

4. Daily MVP + Clutch/Int awards
5. Head-to-head command (`!vs Name1 Name2`) for day/week
6. Weekly title belts (Damage King, Objective Goblin, Vision Dad)
7. Prediction game for day record guesses
8. Profile command (`!profile Name#Tag`) with trend and best queue
9. Party synergy stats for duo/trio combinations
10. Seasonal month-long points race
11. Clip/quote of the day in recap flow
12. Weekly boss challenge mode with success/fail announcement

## Recently Completed (Removed From Backlog)

- Runtime + DB + command module split completed.
- Streak callouts moved to separate messages and TTS toggle added.
- `!tts` routing allowed in events + recap channels.
- Command routing matrix tests added.
- Recap/streak separation integration test coverage added.
- GitLab test pipeline tightened for push + MR.
