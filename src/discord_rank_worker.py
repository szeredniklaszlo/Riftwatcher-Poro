import asyncio

import requests

from src.rank_logic import format_rank_change_message, normalize_queue_type


async def process_rank_cycle(
    *,
    friends,
    channel,
    riot_client,
    db_load_ranked_state,
    db_upsert_ranked_state,
    db_delete_ranked_state_queue,
    log,
):
    for riot_id in friends:
        try:
            previous_rows = await asyncio.to_thread(db_load_ranked_state, riot_id)
            previous_by_queue = {}
            for row in previous_rows:
                queue_type = normalize_queue_type(row["queue_type"]) or row["queue_type"]
                previous_by_queue[queue_type] = {
                    "tier": row["tier"],
                    "rank_division": row["rank_division"],
                    "league_points": int(row["league_points"] or 0),
                    "wins": int(row["wins"] or 0),
                    "losses": int(row["losses"] or 0),
                    "hot_streak": bool(row["hot_streak"]),
                    "veteran": bool(row["veteran"]),
                    "fresh_blood": bool(row["fresh_blood"]),
                    "inactive": bool(row["inactive"]),
                }

            current_entries_raw = await riot_client.fetch_ranked_entries(riot_id)
            current_by_queue = {}
            for entry in current_entries_raw:
                queue_type = normalize_queue_type(entry.get("queueType"))
                if queue_type is None:
                    continue
                current_by_queue[queue_type] = entry

            # First observation for this player: persist baseline without notifications.
            if not previous_by_queue:
                for queue_type, entry in current_by_queue.items():
                    await asyncio.to_thread(db_upsert_ranked_state, riot_id, queue_type, entry)
                continue

            for queue_type in sorted(set(previous_by_queue.keys()) | set(current_by_queue.keys())):
                previous_entry = previous_by_queue.get(queue_type)
                current_entry = current_by_queue.get(queue_type)
                message = format_rank_change_message(riot_id, queue_type, previous_entry, current_entry)
                if message:
                    await channel.send(message)
                    log(f"[rank] Rank change posted for {riot_id} ({queue_type}).")

            for queue_type, entry in current_by_queue.items():
                await asyncio.to_thread(db_upsert_ranked_state, riot_id, queue_type, entry)
            for queue_type in previous_by_queue.keys():
                if queue_type not in current_by_queue:
                    await asyncio.to_thread(db_delete_ranked_state_queue, riot_id, queue_type)
        except requests.RequestException as exc:
            log(f"[rank] Failed rank-check for {riot_id}: {exc}")
        except Exception as exc:
            log(f"[rank] Unexpected rank-check error for {riot_id}: {exc}")
