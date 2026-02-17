# MoodBot

MoodBot is a Discord bot that tracks your group's League of Legends performance for today and posts a clean mood board in Discord.

It pulls live data from Riot's APIs, calculates each player's daily record, ranks everyone by win rate, and keeps no-match players at the bottom.

## What It Does

- Connects to Discord and listens in one configured channel.
- Fetches player account and match data from Riot API.
- Builds a "today only" report:
  - Wins / losses
  - Win rate percentage
  - Mood emoji (green/yellow/red)
- Sorts players from best to worst win rate.
- Shows players with no matches today at the end.
- Responds to `!Mood` with:
  - A quick "working..." message
  - Then edits that message into the final formatted report
- Also posts a scheduled daily report at 20:00 local time.

## Commands

- `!Mood` - Generate and post today's ranked mood report.
- `!test` - Simple Discord send test.
- `!riottest` - Basic Riot connectivity test.

## Tech Stack

- Python 3.11+
- `discord.py`
- `requests`

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install discord.py requests
python Bot.py
```

## How The Report Is Calculated

1. Resolve each Riot ID (`gameName#tagLine`) to `puuid`.
2. Pull recent matches from Match-V5.
3. Keep only matches completed today (local date).
4. Count wins and losses for each player.
5. Compute win rate and sort descending.
6. Append no-match players at the bottom.

## Notes

- The bot currently uses hardcoded config values in `Bot.py` (token, API key, channel, players).
- For production use, move secrets back to environment variables or a local config file that is not committed.
