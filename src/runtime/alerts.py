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
