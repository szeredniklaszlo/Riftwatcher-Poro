import asyncio


class RiotAlertState:
    def __init__(self):
        self.riot_401_alert_sent = False
        self.riot_alert_lock = asyncio.Lock()


async def send_riot_key_expired_alert(*, resolve_channel, events_channel_id, log):
    channel = await resolve_channel(events_channel_id)
    if channel is None:
        return False
    await channel.send(
        "@NoxVain \u26A0\uFE0F Riot API returned 401 Unauthorized. "
        "Your RIOT_API_KEY is likely expired or invalid. "
        "Update the Railway variable `RIOT_API_KEY`."
    )
    log("[riot] Sent RIOT_API_KEY expiry alert.")
    return True


def riot_401_alert_already_sent(*, state: RiotAlertState, db_get_state):
    if state.riot_401_alert_sent:
        return True
    persisted = db_get_state("riot_401_alert_sent")
    if persisted == "1":
        state.riot_401_alert_sent = True
        return True
    return False


def mark_riot_401_alert_sent(*, state: RiotAlertState, db_set_state):
    state.riot_401_alert_sent = True
    db_set_state("riot_401_alert_sent", "1")


def trigger_riot_key_alert(
    *,
    state: RiotAlertState,
    client,
    resolve_channel,
    events_channel_id,
    db_get_state,
    db_set_state,
    log,
):
    async def _inner():
        async with state.riot_alert_lock:
            if riot_401_alert_already_sent(state=state, db_get_state=db_get_state):
                return
            try:
                sent = await send_riot_key_expired_alert(
                    resolve_channel=resolve_channel,
                    events_channel_id=events_channel_id,
                    log=log,
                )
            except Exception as exc:
                log(f"[riot] Failed to send RIOT_API_KEY expiry alert: {exc}")
                return
            if sent:
                mark_riot_401_alert_sent(state=state, db_set_state=db_set_state)

    try:
        loop = client.loop
        asyncio.run_coroutine_threadsafe(_inner(), loop)
    except Exception as exc:
        log(f"[riot] Could not schedule key-expiry alert: {exc}")


def worker_stall_state_key(worker_name):
    return f"worker_stall_alert_sent::{worker_name}"


async def check_and_notify_worker_stalls(
    *,
    state,
    resolve_channel,
    events_channel_id,
    worker_stats,
    stale_thresholds_seconds,
    db_get_state=None,
    db_set_state=None,
    now_monotonic,
    log,
):
    channel = await resolve_channel(events_channel_id)
    if channel is None:
        return

    alerted_by_worker = state.setdefault("alerted_by_worker", {})

    for worker_name, threshold_seconds in stale_thresholds_seconds.items():
        entry = worker_stats.get(worker_name) or {}
        runs = int(entry.get("runs", 0) or 0)
        if runs <= 0:
            continue

        last_success_at = float(entry.get("last_success_at", 0.0) or 0.0)
        if last_success_at <= 0:
            continue

        stale_for = now_monotonic - last_success_at
        is_stale = stale_for >= float(threshold_seconds)
        alerted = alerted_by_worker.get(worker_name)
        if alerted is None and db_get_state is not None:
            persisted = await asyncio.to_thread(db_get_state, worker_stall_state_key(worker_name))
            alerted = persisted == "1"
            alerted_by_worker[worker_name] = alerted
        if alerted is None:
            alerted = False
            alerted_by_worker[worker_name] = False

        if is_stale and not alerted:
            await channel.send(
                f"\u26A0\uFE0F Worker `{worker_name}` appears stalled. "
                f"No successful cycle for `{int(stale_for)}s` (threshold `{int(threshold_seconds)}s`)."
            )
            alerted_by_worker[worker_name] = True
            if db_set_state is not None:
                await asyncio.to_thread(db_set_state, worker_stall_state_key(worker_name), "1")
            log(
                f"[health] Worker stall alert sent for {worker_name}: "
                f"stale_for={int(stale_for)}s threshold={int(threshold_seconds)}s"
            )
            continue

        if (not is_stale) and alerted:
            await channel.send(
                f"\u2705 Worker `{worker_name}` recovered. "
                f"Latest successful cycle was `{int(now_monotonic - last_success_at)}s` ago."
            )
            alerted_by_worker[worker_name] = False
            if db_set_state is not None:
                await asyncio.to_thread(db_set_state, worker_stall_state_key(worker_name), "0")
            log(f"[health] Worker stall cleared for {worker_name}.")
