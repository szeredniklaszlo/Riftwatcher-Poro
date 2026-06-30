import asyncio
from datetime import datetime

import requests

from src import config as cfg
from src.arena_static import load_arena_display_names
from src.discord_text import (
    ARENA_QUEUE_IDS,
    format_match_duration,
    get_arena_placement,
    get_arena_subteam_id,
    format_recap_player_line,
    format_recap_queue_name,
    format_streak_callout,
    parse_streak_tts_enabled,
    match_recap_state_key,
    streak_callout_state_key,
    streak_tts_enabled_state_key,
)
from src.report_logic import derive_primary_role, get_match_duration_seconds, get_match_end_unix_seconds, get_mode_bucket, is_remake_match
from src.discord_ui import MatchRecapView
from src.static_data import get_static_data


async def get_ranked_streak_info(riot_client, puuid, recent_ids, max_matches=20):
    streak_result = None
    streak_count = 0
    for match_id in recent_ids[:max(1, max_matches)]:
        match_info = await riot_client.fetch_match_info(match_id)
        if is_remake_match(match_info):
            continue
        queue_id = int(match_info.get("info", {}).get("queueId", -1))
        if get_mode_bucket(queue_id) is None:
            continue
        participant = riot_client.get_participant(match_info, puuid)
        if participant is None:
            continue
        won = bool(participant.get("win"))
        if streak_result is None:
            streak_result = won
            streak_count = 1
            continue
        if won == streak_result:
            streak_count += 1
            continue
        break
    if streak_result is None:
        return 0, None
    return streak_count, streak_result


def _pack_sections_into_messages(sections, separator, max_len=2000):
    messages = []
    current = []
    for section in sections:
        candidate = separator.join(current + [section]) if current else section
        if len(candidate) <= max_len:
            current.append(section)
        elif current:
            messages.append(separator.join(current))
            current = [section]
        else:
            messages.append(section[:max_len - 50] + "\n...")
    if current:
        messages.append(separator.join(current))
    return messages


def _recap_participant_sort_key(queue_id, row):
    riot_id, participant = row
    if queue_id in ARENA_QUEUE_IDS:
        placement = get_arena_placement(participant)
        subteam_id = get_arena_subteam_id(participant)
        safe_placement = placement if placement is not None else 99
        safe_subteam_id = subteam_id if isinstance(subteam_id, int) else 99
        return (safe_placement, safe_subteam_id, riot_id.casefold())
    return (riot_id.casefold(),)


async def process_recap_cycle(
    *,
    friends,
    riot_client,
    poro_service,
    report_timezone,
    match_recap_channel_id,
    channel,
    db_enabled,
    db_get_state,
    db_set_state,
    db_upsert_daily_stats,
    edit_last_report_message,
    edit_last_weekly_report_message=None,
    log,
):
    recap_split_spacing_seconds = 3.0
    recap_section_separator = "\n\n---\n\n"
    puuid_by_riot_id = {}
    recent_ids_by_riot_id = {}
    matches_to_report = set()
    pending_latest_match_id_by_riot = {}
    pending_new_match_ids_by_riot = {}
    checked_players = 0
    players_with_recent_ids = 0
    initialized_players = 0
    players_with_new_ids = 0
    for riot_id in friends:
        try:
            checked_players += 1
            puuid = await riot_client.fetch_puuid(riot_id)
            puuid_by_riot_id[riot_id] = puuid
            recent_ids = await riot_client.fetch_recent_match_ids(puuid, count=20, riot_id=riot_id)
            recent_ids_by_riot_id[riot_id] = recent_ids
            if not recent_ids:
                continue

            players_with_recent_ids += 1
            state_key = match_recap_state_key(riot_id)
            last_announced = await asyncio.to_thread(db_get_state, state_key)
            latest_match_id = recent_ids[0]
            if not last_announced:
                await asyncio.to_thread(db_set_state, state_key, latest_match_id)
                initialized_players += 1
                continue

            new_match_ids = poro_service.get_new_match_ids(recent_ids, last_announced)
            if new_match_ids:
                matches_to_report.update(new_match_ids)
                pending_latest_match_id_by_riot[riot_id] = latest_match_id
                pending_new_match_ids_by_riot[riot_id] = set(new_match_ids)
                players_with_new_ids += 1
        except requests.RequestException as exc:
            log(f"[recap] Failed while checking {riot_id}: {exc}")

    if not matches_to_report:
        log(
            "[recap] No new matches to post: "
            f"checked_players={checked_players} players_with_recent_ids={players_with_recent_ids} "
            f"initialized_players={initialized_players} players_with_new_ids={players_with_new_ids}."
        )
        return

    puuid_to_riot_id = {puuid: riot_id for riot_id, puuid in puuid_by_riot_id.items()}
    match_entries = []
    failed_match_ids = set()
    skipped_no_tracked_participants = 0
    skipped_remakes = 0
    for match_id in matches_to_report:
        try:
            match_info = await riot_client.fetch_match_info(match_id)
        except requests.RequestException as exc:
            failed_match_ids.add(match_id)
            log(f"[recap] Failed fetching match {match_id}: {exc}")
            continue

        participants = match_info.get("info", {}).get("participants", [])
        tracked_participants = []
        for participant in participants:
            riot_id = puuid_to_riot_id.get(participant.get("puuid"))
            if riot_id:
                tracked_participants.append((riot_id, participant))
        if not tracked_participants:
            skipped_no_tracked_participants += 1
            continue

        end_ts = get_match_end_unix_seconds(match_info)
        queue_id = int(match_info.get("info", {}).get("queueId", -1))
        if is_remake_match(match_info):
            skipped_remakes += 1
            continue
        duration_seconds = get_match_duration_seconds(match_info)
        match_entries.append((end_ts, match_id, queue_id, duration_seconds, tracked_participants))

    log(
        "[recap] Match scan summary: "
        f"candidate_matches={len(matches_to_report)} prepared_matches={len(match_entries)} "
        f"failed_fetches={len(failed_match_ids)} skipped_no_tracked={skipped_no_tracked_participants} "
        f"skipped_remakes={skipped_remakes}."
    )

    match_entries.sort(key=lambda row: row[0])

    recap_sections = []
    recap_messages_payload = [] # Itt tároljuk a Rich Embedeket
    arena_display_names = None

    for end_ts, match_id, queue_id, duration_seconds, tracked_participants in match_entries:

        # =====================================================================
        # V2.0: RICH EMBED NÉZET (OPCIONÁLIS)
        # =====================================================================
        if getattr(cfg, "ENABLE_RICH_RECAPS", False):
            try:
                static_data = get_static_data() # Lusta betöltés (Lazy Load)

                match_info = await riot_client.fetch_match_info(match_id)
                participants = match_info.get("info", {}).get("participants", [])
                queue_name = format_recap_queue_name(queue_id)
                end_local = datetime.fromtimestamp(end_ts, tz=report_timezone)
                duration_label = format_match_duration(duration_seconds)

                # A figyelt játékos adatai
                primary_friend_riot_id = tracked_participants[0][0]
                primary_friend_puuid = puuid_by_riot_id[primary_friend_riot_id]
                is_win = False
                primary_champ = "Poro"

                for p in participants:
                    if p.get("puuid") == primary_friend_puuid:
                        is_win = p.get("win", False)
                        primary_champ = p.get("championName", "Poro")
                        break

                import discord
                from src.discord_ui import apply_player_summary_fields
                embed_color = discord.Color.green() if is_win else discord.Color.red()

                # A játékos szerepe és hőse
                primary_p = None
                for p in participants:
                    if p.get("puuid") == primary_friend_puuid:
                        primary_p = p
                        break

                raw_champ = primary_p.get("championName", "Poro") if primary_p else "Poro"
                champ_display = static_data.get("champions", {}).get(raw_champ, raw_champ)
                role = str(primary_p.get("teamPosition", "")).upper()[:3] if primary_p else "ANY"
                if role == "UTI": role = "SUP"

                # 1. CÍM (Title) - Új, tökéletes dizájn
                short_name = primary_friend_riot_id.split('#')[0]
                rank_suffix = ""

                if queue_id in (420, 440):
                    try:
                        ranked_entries = await riot_client.fetch_ranked_entries(primary_friend_riot_id)
                        queue_type = "RANKED_SOLO_5x5" if queue_id == 420 else "RANKED_FLEX_SR"
                        for entry in ranked_entries:
                            if entry.get("queueType") == queue_type:
                                tier = str(entry.get("tier", "")).title()
                                rank = str(entry.get("rank", ""))
                                lp = entry.get("leaguePoints", 0)
                                rank_suffix = f" • {tier} {rank} ({lp} LP)"
                                break
                    except Exception as e:
                        log(f"[recap] Rank fetch timeout/error for {primary_friend_riot_id}: {e}")

                # Példa: 🏆 Ranked Solo/Duo • MID • Katarina (Joacoking) • Emerald IV (44 LP)
                embed_title = f"{queue_name} • {role} • {champ_display} ({short_name}){rank_suffix}"

                # 2. LÁBJEGYZET (Footer) - Letisztítva
                region_raw = match_id.split("_")[0].upper()
                region_display = "EUNE" if region_raw == "EUN1" else ("EUW" if region_raw == "EUW1" else region_raw)

                ally_friends = []
                for p in participants:
                    if p.get("puuid") in puuid_by_riot_id.values():
                        ally_name = p.get("riotIdGameName") or p.get("summonerName") or "Unknown"
                        ally_friends.append(ally_name)
                allies_text = f" • Allies: {', '.join(ally_friends)}" if ally_friends else ""

                footer_text = f"Region: {region_display}{allies_text}\nFinished: {end_local:%Y.%m.%d %H:%M} • ⏱️ {duration_label}"

                # 3. Aktuális Rang Lekérdezése
                current_rank_text = ""
                if queue_id in (420, 440):
                    try:
                        ranked_entries = await riot_client.fetch_ranked_entries(primary_friend_riot_id)
                        queue_type = "RANKED_SOLO_5x5" if queue_id == 420 else "RANKED_FLEX_SR"
                        for entry in ranked_entries:
                            if entry.get("queueType") == queue_type:
                                tier = str(entry.get("tier", "")).title()
                                rank = str(entry.get("rank", ""))
                                lp = entry.get("leaguePoints", 0)
                                current_rank_text = f" • {tier} {rank} ({lp} LP)"
                                break
                    except Exception as e:
                        log(f"[recap] Rank fetch timeout/error for {primary_friend_riot_id}: {e}")

                timeline_data = None
                try:
                    timeline_data = await riot_client.fetch_match_timeline(match_id)
                except Exception as e:
                    log(f"[recap] Timeline fetch timeout/error for {match_id}: {e}")

                tier_str = current_rank_text.split("(")[0].replace("•", "").strip() if current_rank_text else "Unranked"
                # Képek URL-jeinek legenerálása
                version = static_data.get("version", "14.1.1")
                profile_icon_id = primary_p.get("profileIcon", 1) if primary_p else 1
                champ_icon_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{raw_champ}.png"
                profile_icon_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{profile_icon_id}.png"
                skin_num = primary_p.get("skin", 0) if primary_p else 0
                splash_url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{raw_champ}_{skin_num}.jpg"

                # --- ARÉNA JÁTÉKOK SZÉTVÁGÁSA 2 ÜZENETBE ---
                is_arena = queue_id in (1700, 1710, 1750)

                if is_arena:
                    def get_placement(p):
                        for field in ("placement", "subteamPlacement", "teamPlacement"):
                            if p.get(field) is not None:
                                return int(p[field])
                        return 99

                    # Sorba rendezés helyezés szerint
                    sorted_parts = sorted(participants, key=get_placement)
                    half = len(sorted_parts) // 2

                    # 2 üzenet lesz belőle!
                    parts_list = [
                        (sorted_parts[:half], " (Top Teams)"),
                        (sorted_parts[half:], " (Bottom Teams)")
                    ]
                else:
                    parts_list = [(participants, "")]

                for parts, title_suffix in parts_list:
                    embed = discord.Embed(color=embed_color)
                    # CÍM ÉS LÁBLÉC KÉPEK BEÁLLÍTÁSA
                    embed.set_author(name=embed_title + title_suffix, icon_url=champ_icon_url)
                    embed.set_footer(text=footer_text, icon_url=profile_icon_url)

                    match_data = {
                        "match_id": match_id,
                        "primary_friend_riot_id": primary_friend_riot_id,
                        "participants": parts, # Már csak az adott üzenet játékosai
                        "primary_p": primary_p,
                        "tier_str": tier_str,
                        "timeline_data": timeline_data,
                        "splash_url": splash_url
                    }
                    view = MatchRecapView(match_data, list(puuid_by_riot_id.values()), static_data)
                    view.apply_scoreboard(embed)

                    recap_messages_payload.append({
                        "embed": embed,
                        "view": view
                    })
                log(f"[recap] Prepared rich embed recap for {match_id}")
            except Exception as e:
                log(f"[recap] Error building rich embed for {match_id}: {e}")

        # =====================================================================
        # V1.0: KLASSZIKUS SZÖVEGES NÉZET (VISSZAFELÉ KOMPATIBILITÁS)
        # =====================================================================
        else:
            queue_name = format_recap_queue_name(queue_id)
            end_local = datetime.fromtimestamp(end_ts, tz=report_timezone)
            duration_label = format_match_duration(duration_seconds)
            lines = [
                "🎮 **New Match Recap**",
                f"`{queue_name}` - 🕒 `{end_local:%d.%m.%Y %H:%M}` - ⏱️ `{duration_label}`",
                "",
            ]
            if queue_id in ARENA_QUEUE_IDS and arena_display_names is None:
                arena_display_names = await asyncio.to_thread(load_arena_display_names)
            augment_names = (arena_display_names or {}).get("augment_names", {})
            item_names = (arena_display_names or {}).get("item_names", {})
            ordered_participants = sorted(tracked_participants, key=lambda row: _recap_participant_sort_key(queue_id, row))
            for index, (riot_id, participant) in enumerate(ordered_participants):
                lines.append(
                    format_recap_player_line(
                        riot_id,
                        participant,
                        duration_seconds,
                        queue_id=queue_id,
                        augment_names=augment_names,
                        item_names=item_names,
                    )
                )
                if index < len(ordered_participants) - 1:
                    lines.append("")
            recap_sections.append("\n".join(lines))
            log(f"[recap] Prepared classic match recap for {match_id}")

    recap_messages = _pack_sections_into_messages(recap_sections, recap_section_separator)

    for riot_id, latest_match_id in pending_latest_match_id_by_riot.items():
        failed_for_player = False
        for match_id in pending_new_match_ids_by_riot.get(riot_id, set()):
            if match_id in failed_match_ids:
                failed_for_player = True
                break
        if failed_for_player:
            log(
                f"[recap] Keeping previous recap state for {riot_id}; "
                "will retry due to fetch failures in this cycle."
            )
            continue
        state_key = match_recap_state_key(riot_id)
        await asyncio.to_thread(db_set_state, state_key, latest_match_id)

    affected_riot_ids = set()
    for _end_ts, _match_id, _queue_id, _duration_seconds, tracked_participants in match_entries:
        for riot_id, _participant in tracked_participants:
            affected_riot_ids.add(riot_id)
    if not affected_riot_ids:
        return

    streak_sections = []
    pending_streak_state_updates = []
    for riot_id in sorted(affected_riot_ids, key=str.casefold):
        puuid = puuid_by_riot_id.get(riot_id)
        recent_ids = recent_ids_by_riot_id.get(riot_id, [])
        if puuid is None or not recent_ids:
            continue
        try:
            streak_count, is_win_streak = await get_ranked_streak_info(riot_client, puuid, recent_ids)
            state_key = streak_callout_state_key(riot_id)
            if streak_count < 3 or is_win_streak is None:
                await asyncio.to_thread(db_set_state, state_key, "none")
                continue

            streak_token = f"{'W' if is_win_streak else 'L'}:{streak_count}"
            last_token = await asyncio.to_thread(db_get_state, state_key)
            if last_token == streak_token:
                continue
            streak_sections.append(format_streak_callout(riot_id, streak_count, is_win_streak))
            pending_streak_state_updates.append((state_key, streak_token, riot_id))
        except requests.RequestException as exc:
            log(f"[recap] Could not build streak callout for {riot_id}: {exc}")
        except Exception as exc:
            log(f"[recap] Streak callout skipped for {riot_id}: {exc}")

    if getattr(cfg, "ENABLE_RICH_RECAPS", False):
        for index, payload in enumerate(recap_messages_payload):
            await channel.send(embed=payload["embed"], view=payload["view"])
            if index < len(recap_messages_payload) - 1:
                await asyncio.sleep(recap_split_spacing_seconds)
        if recap_messages_payload:
            log(f"[recap] Posted RICH recap batch in channel {match_recap_channel_id}: matches={len(recap_messages_payload)}.")
    else:
        for index, recap_message in enumerate(recap_messages):
            await channel.send(recap_message)
            if index < len(recap_messages) - 1:
                await asyncio.sleep(recap_split_spacing_seconds)
        if recap_messages:
            log(f"[recap] Posted CLASSIC recap batch in channel {match_recap_channel_id}: matches={len(recap_sections)} messages={len(recap_messages)}.")

    streak_tts_enabled = True
    try:
        raw_tts_state = await asyncio.to_thread(db_get_state, streak_tts_enabled_state_key())
        streak_tts_enabled = parse_streak_tts_enabled(raw_tts_state, default=True)
    except Exception as exc:
        log(f"[recap] Could not read streak TTS setting: {exc}")

    for streak_message in streak_sections:
        await channel.send(streak_message, tts=streak_tts_enabled)
    if streak_sections:
        log(
            f"[recap] Posted streak callout batch in channel {match_recap_channel_id}: "
            f"streaks={len(streak_sections)} tts={str(streak_tts_enabled).lower()}."
        )
    for state_key, streak_token, riot_id in pending_streak_state_updates:
        await asyncio.to_thread(db_set_state, state_key, streak_token)
        log(f"[recap] Posted streak callout for {riot_id} ({streak_token}).")

    if not db_enabled:
        return

    try:
        cycle_key = poro_service.get_cycle_key()

        for riot_id in sorted(affected_riot_ids, key=str.casefold):
            mode_records, performance_totals = await riot_client.get_today_mode_records(riot_id)
            primary_role = derive_primary_role(performance_totals)
            await asyncio.to_thread(
                db_upsert_daily_stats,
                cycle_key,
                riot_id,
                mode_records,
                performance_totals,
                primary_role,
            )

        poro_service.invalidate_report_cache()
        await edit_last_report_message(bypass_cache=True)
        if edit_last_weekly_report_message is not None:
            await edit_last_weekly_report_message(bypass_cache=True)
        log(
            f"[recap] Synced daily report after posting new match recap(s). "
            f"affected_players={len(affected_riot_ids)}"
        )
    except Exception as exc:
        log(f"[recap] Failed to sync daily report after recap: {exc}")
