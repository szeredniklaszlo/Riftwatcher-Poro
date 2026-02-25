import asyncio
from datetime import timedelta

import requests

from src.constants import (
    ADD_COMMAND,
    HEALTH_COMMAND,
    HELP_COMMAND,
    RIOT_TEST_COMMAND,
    SCORE_COMMAND,
    TEST_COMMAND,
    TTS_COMMAND,
)
from src.discord_text import parse_streak_tts_enabled, streak_tts_enabled_state_key


async def handle_ops_commands(ctx):
    content = ctx.content
    content_lower = ctx.content_lower

    if content_lower == HELP_COMMAND.casefold():
        from src.commands.routing import format_help_text

        await ctx.message.channel.send(
            format_help_text(
                report_day_start_hour=ctx.report_day_start_hour,
                daily_channel_id=ctx.daily_channel_id,
                weekly_channel_id=ctx.weekly_channel_id,
                events_channel_id=ctx.events_channel_id,
                match_recap_channel_id=ctx.match_recap_channel_id,
            )
        )
        return True

    if content_lower == TEST_COMMAND.casefold():
        await ctx.message.channel.send("API test: MoodBot is online and can send messages.")
        ctx.log(f"[test] Sent API test message in channel {ctx.message.channel.id}.")
        return True

    if content_lower == RIOT_TEST_COMMAND.casefold():
        if not ctx.friends:
            await ctx.message.channel.send(
                f"Riot API test skipped: no tracked players in database. Add one with `{ADD_COMMAND} Name#Tag`."
            )
            return True
        try:
            riot_id, puuid, match_count = await ctx.riot_client.run_riot_connectivity_test(ctx.friends[0])
            await ctx.message.channel.send(
                f"Riot API test OK for `{riot_id}`. Retrieved puuid and {match_count} matches."
            )
            ctx.log(f"[test] Riot API test succeeded for {riot_id} ({puuid[:8]}...).")
        except (KeyError, requests.RequestException) as exc:
            await ctx.message.channel.send(f"Riot API test failed: {exc}")
            ctx.log(f"[test] Riot API test failed: {exc}")
        return True

    if content_lower == HEALTH_COMMAND.casefold():
        stats = await ctx.mood_service.run_health_check(ctx.start_monotonic, worker_stats=ctx.worker_stats)
        uptime = str(timedelta(seconds=stats["uptime_seconds"]))
        top_backfill_offsets = ", ".join(stats.get("top_backfill_offsets", [])) or "none"
        wstats = stats.get("worker_stats") or {}
        workers_line = ""
        if wstats:
            parts = [f"{k}: {v['cycles']}ok/{v['errors']}err" for k, v in wstats.items()]
            workers_line = f"\n- Workers: `{' | '.join(parts)}`"
        baseline_age_seconds = stats.get("baseline_age_seconds")
        if baseline_age_seconds is None:
            baseline_line = "\n- Gamer Score baselines: `not yet built`"
        else:
            age = str(timedelta(seconds=baseline_age_seconds))
            baseline_line = (
                f"\n- Gamer Score baselines: "
                f"`{stats['baseline_roles']} roles, {stats['baseline_samples']} samples (built {age} ago)`"
            )
        await ctx.message.channel.send(
            (
                "Health OK\n"
                f"- Uptime: `{uptime}`\n"
                f"- Tracked players: `{stats['tracked_players']}`\n"
                f"- DB: `{'ok' if stats['db_ok'] else 'down'}`\n"
                f"- Match cache entries: `{stats['match_cache_entries']}`\n"
                f"- Report cache active: `{'yes' if stats['request_cache_active'] else 'no'}`\n"
                f"- Backfill cursors active: `{stats.get('players_with_backfill_offset', 0)}/{stats['tracked_players']}`\n"
                f"- Backfill max offset: `{stats.get('max_backfill_offset', 0)}`\n"
                f"- Backfill top offsets: `{top_backfill_offsets}`"
                f"{baseline_line}"
                f"{workers_line}"
            )
        )
        ctx.log("[health] Sent health status message.")
        return True

    if content_lower == SCORE_COMMAND.casefold():
        report = await ctx.mood_service.build_score_breakdown_report()
        await ctx.message.channel.send(report)
        ctx.log("[score] Sent score breakdown.")
        return True

    if content_lower == TTS_COMMAND.casefold():
        await ctx.message.channel.send(f"Usage: `{TTS_COMMAND} on|off|status`")
        return True

    if content_lower.startswith(f"{TTS_COMMAND.casefold()} "):
        arg = content[len(TTS_COMMAND):].strip().lower()
        state_key = streak_tts_enabled_state_key()
        if arg == "status":
            raw_value = None
            if ctx.db_get_state is not None:
                raw_value = await asyncio.to_thread(ctx.db_get_state, state_key)
            enabled = parse_streak_tts_enabled(raw_value, default=True)
            await ctx.message.channel.send(
                f"Streak alert TTS is currently `{'ON' if enabled else 'OFF'}`."
            )
            return True
        if arg not in {"on", "off"}:
            await ctx.message.channel.send(f"Usage: `{TTS_COMMAND} on|off|status`")
            return True

        enabled = arg == "on"
        if ctx.db_set_state is not None:
            await asyncio.to_thread(ctx.db_set_state, state_key, "1" if enabled else "0")
        await ctx.message.channel.send(
            f"Streak alert TTS is now `{'ON' if enabled else 'OFF'}`."
        )
        ctx.log(f"[tts] Streak alert TTS set to {'ON' if enabled else 'OFF'}.")
        return True

    return False
