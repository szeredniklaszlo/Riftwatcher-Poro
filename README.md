# MoodBot

MoodBot is a Discord bot that tracks League match mood for a tracked player list and posts a live scoreboard in one Discord channel.

## Current Structure

- `src/app.py` - module entrypoint used by Railway
- `src/discord_bot.py` - Discord runtime and command handlers
- `src/config.py` - environment/config loading
- `src/db.py` - Postgres pool and persistence layer
- `src/riot_api.py` - Riot API client (account, match list, match details, retries)
- `src/mood_service.py` - report building, snapshot/cache flow, refresh orchestration
- `src/report_logic.py` - pure ranking and formatting helpers
- `src/constants.py` - command constants
- `tests/test_report_logic.py` - unit tests for ranking/window logic helpers
- `README.md` - project docs

## Features

- `!Mood` posts/updates a single scoreboard message.
- Rolling daily window starting at **06:00** in `REPORT_TIMEZONE`.
- Per-player breakdown:
  - Total
  - Ranked Solo/Duo
  - Ranked Flex
- Ranking based on Wilson lower bound (`z=1.28`).
- Displays `Gamer Score` (Wilson score x 100) per player.
- Background refresh stores/reuses data in Postgres.
- Background refresh updates the live scoreboard during long refresh cycles (at least every ~2 minutes, and no more than every ~30s on content changes).
- Persistent match cache and scoreboard message ID in Postgres.
- Structured logging with optional JSON output and per-request IDs.
- Automatic cleanup of cached match payloads (default retention: 31 days).
- `!Add Name#Tag` adds players at runtime and persists to Postgres.
- `!DebugPlayer Name#Tag` prints queue/category mapping for recent games.

## Commands

- `!Mood`
- `!Add Name#Tag`
- `!DebugPlayer Name#Tag`
- `!health`
- `!test`
- `!riottest`

## Environment Variables

Required:

- `DISCORD_TOKEN`
- `RIOT_API_KEY`
- `DISCORD_CHANNEL_ID`
- `DATABASE_URL`

Optional:

- `REPORT_TIMEZONE` (default: `UTC`, example: `Europe/Oslo`)
- `LOG_RIOT_REQUESTS` (default: `false`)
- `LOG_JSON` (default: `false`, emits JSON logs with request IDs)
- `MAX_TODAY_MATCH_DETAILS` (default: `20`)
- `REPORT_DAY_START_HOUR` (default: `6`, daily report window start hour in `REPORT_TIMEZONE`)
- `MAX_MATCH_IDS_SCAN` (default: `300`, caps per-player match ID paging in the active report window)
- `MAX_IN_MEMORY_MATCH_CACHE` (default: `200`, caps in-process cached match payloads)
- `REPORT_CACHE_SECONDS` (default: `120`)
- `DAILY_REFRESH_SECONDS` (default: `300`)
- `DB_POOL_SIZE` (default: `5`)
- `MATCH_CACHE_RETENTION_DAYS` (default: `31`)

## Tests

```bash
pytest -q
```

Pytest cache provider is disabled in `pytest.ini` to avoid creating local `.pytest_cache` / `pytest-cache-files-*` artifacts.

## Railway

- `Procfile`: `worker: python -m src.app`
- `railway.json` start command: `python -m src.app`
- GitLab CI deploy uses Railway CLI from `.gitlab-ci.yml`

Runtime variables to set in Railway:

- `DISCORD_TOKEN`
- `RIOT_API_KEY`
- `DISCORD_CHANNEL_ID`
- `DATABASE_URL`
- Optional tuning variables from above
