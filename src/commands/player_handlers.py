import asyncio

import requests

from src.constants import ADD_COMMAND, DEBUG_PLAYER_COMMAND, STREAK_COMMAND
from src.discord_recap_worker import get_ranked_streak_info
from src.discord_text import (
    format_streak_callout,
    parse_streak_tts_enabled,
    streak_callout_state_key,
    streak_tts_enabled_state_key,
)


async def handle_player_commands(ctx):
    content = ctx.content
    content_lower = ctx.content_lower

    if content_lower == DEBUG_PLAYER_COMMAND.casefold():
        await ctx.message.channel.send(f"Usage: `{DEBUG_PLAYER_COMMAND} Name#Tag`")
        return True

    if content_lower.startswith(f"{DEBUG_PLAYER_COMMAND.casefold()} "):
        raw_riot_id = content[len(DEBUG_PLAYER_COMMAND):].strip()
        status_message = await ctx.message.channel.send(f"\u23F3 Building debug report for `{raw_riot_id}`...")
        try:
            report_text = await ctx.riot_client.build_debug_player_report(
                raw_riot_id,
                report_timezone_name=ctx.report_timezone_name,
                normalize_riot_id=ctx.normalize_riot_id,
            )
            if len(report_text) > 1900:
                report_text = report_text[:1900] + "\n...truncated..."
            await status_message.edit(content=f"```text\n{report_text}\n```")
        except ValueError as exc:
            await status_message.edit(content=f"Debug report failed: {exc}")
        except (KeyError, requests.RequestException) as exc:
            await status_message.edit(content=f"Debug report failed: {exc}")
            ctx.log(f"[debug] Debug report failed: {exc}")
        return True

    if content_lower == STREAK_COMMAND.casefold():
        await ctx.message.channel.send(f"Usage: `{STREAK_COMMAND} Name#Tag`")
        return True

    if content_lower.startswith(f"{STREAK_COMMAND.casefold()} "):
        raw_riot_id = content[len(STREAK_COMMAND):].strip()
        try:
            riot_id = ctx.normalize_riot_id(raw_riot_id)
        except ValueError as exc:
            await ctx.message.channel.send(f"Streak lookup failed: {exc}")
            return True
        status_message = await ctx.message.channel.send(f"\u23F3 Looking up streak for `{riot_id}`...")
        try:
            puuid = await ctx.riot_client.fetch_puuid(riot_id)
            recent_ids = await ctx.riot_client.fetch_recent_match_ids(puuid, count=20, riot_id=riot_id)
            streak_count, is_win_streak = await get_ranked_streak_info(ctx.riot_client, puuid, recent_ids)
            if streak_count < 3 or is_win_streak is None:
                await status_message.edit(content=f"`{riot_id}` has no active ranked streak (fewer than 3 in a row).")
            else:
                callout = format_streak_callout(riot_id, streak_count, is_win_streak)
                await status_message.delete()
                tts_enabled = True
                if ctx.db_get_state is not None:
                    raw_tts = await asyncio.to_thread(ctx.db_get_state, streak_tts_enabled_state_key())
                    tts_enabled = parse_streak_tts_enabled(raw_tts, default=True)
                await ctx.message.channel.send(callout, tts=tts_enabled)
                if ctx.db_set_state is not None:
                    streak_token = f"{'W' if is_win_streak else 'L'}:{streak_count}"
                    await asyncio.to_thread(ctx.db_set_state, streak_callout_state_key(riot_id), streak_token)
                ctx.log(f"[streak] Manual streak callout posted for {riot_id} ({streak_count} {'wins' if is_win_streak else 'losses'}).")
        except (KeyError, requests.RequestException) as exc:
            await status_message.edit(content=f"Streak lookup failed for `{riot_id}`: {exc}")
            ctx.log(f"[streak] Streak lookup failed for {riot_id}: {exc}")
        return True

    if content_lower == ADD_COMMAND.casefold():
        await ctx.message.channel.send(f"Usage: `{ADD_COMMAND} Name#Tag`")
        return True

    if content_lower.startswith(f"{ADD_COMMAND.casefold()} "):
        raw_riot_id = content[len(ADD_COMMAND):].strip()
        try:
            riot_id = ctx.normalize_riot_id(raw_riot_id)
        except ValueError as exc:
            await ctx.message.channel.send(f"Add failed: {exc}")
            return True

        if any(existing.casefold() == riot_id.casefold() for existing in ctx.friends):
            await ctx.message.channel.send(f"`{riot_id}` is already tracked.")
            return True

        status_message = await ctx.message.channel.send(f"\u23F3 Validating `{riot_id}` with Riot API...")
        try:
            await ctx.riot_client.fetch_puuid(riot_id)
        except (KeyError, requests.RequestException) as exc:
            await status_message.edit(content=f"Add failed for `{riot_id}`: {exc}")
            return True

        ctx.friends.append(riot_id)
        try:
            await asyncio.to_thread(ctx.db_upsert_player, riot_id, None)
        except Exception as exc:
            await status_message.edit(content=f"Added `{riot_id}`, but failed to persist to postgres: {exc}")
            return True

        await status_message.edit(
            content=(
                f"\u2705 Added `{riot_id}` and saved to postgres. "
                f"Total tracked players: {len(ctx.friends)}"
            )
        )
        ctx.mood_service.invalidate_report_cache()
        ctx.log(f"[add] Added player {riot_id}.")
        return True

    return False
