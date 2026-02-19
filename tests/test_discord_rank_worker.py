import asyncio

import requests

from src.discord_rank_worker import process_rank_cycle


def _row(queue_type, tier, division, lp=0):
    return (queue_type, tier, division, lp, 0, 0, False, False, False, False, None)


class FakeChannel:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


class FakeRiotClient:
    def __init__(self):
        self.by_player = {}

    async def fetch_ranked_entries(self, riot_id):
        value = self.by_player[riot_id]
        if isinstance(value, Exception):
            raise value
        return value


def test_process_rank_cycle_baseline_persists_without_notifications():
    channel = FakeChannel()
    riot = FakeRiotClient()
    riot.by_player["Alpha#EUW"] = [
        {"queueType": "RANKED_SOLO_5x5", "tier": "SILVER", "rank": "II", "leaguePoints": 55},
        {"queueType": "RANKED_FLEX_SR", "tier": "GOLD", "rank": "IV", "leaguePoints": 10},
    ]
    state = {}
    upserts = []

    def db_load_ranked_state(riot_id):
        return state.get(riot_id, [])

    def db_upsert_ranked_state(riot_id, queue_type, entry):
        upserts.append((riot_id, queue_type, entry["tier"], entry["rank"]))

    asyncio.run(
        process_rank_cycle(
            friends=["Alpha#EUW"],
            channel=channel,
            riot_client=riot,
            db_load_ranked_state=db_load_ranked_state,
            db_upsert_ranked_state=db_upsert_ranked_state,
            db_delete_ranked_state_queue=lambda _riot_id, _queue_type: None,
            log=lambda _msg: None,
        )
    )

    assert channel.messages == []
    assert len(upserts) == 2


def test_process_rank_cycle_sends_rank_up_and_rank_down_once_each():
    channel = FakeChannel()
    riot = FakeRiotClient()
    riot.by_player["Alpha#EUW"] = [
        {"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "IV", "leaguePoints": 12},
        {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I", "leaguePoints": 80},
    ]
    state = {
        "Alpha#EUW": [
            _row("RANKED_SOLO_5x5", "SILVER", "I"),
            _row("RANKED_FLEX_SR", "GOLD", "IV"),
        ]
    }

    asyncio.run(
        process_rank_cycle(
            friends=["Alpha#EUW"],
            channel=channel,
            riot_client=riot,
            db_load_ranked_state=lambda riot_id: state.get(riot_id, []),
            db_upsert_ranked_state=lambda _riot_id, _queue_type, _entry: None,
            db_delete_ranked_state_queue=lambda _riot_id, _queue_type: None,
            log=lambda _msg: None,
        )
    )

    assert len(channel.messages) == 2
    assert any("Rank Up" in msg for msg in channel.messages)
    assert any("Rank Down" in msg for msg in channel.messages)


def test_process_rank_cycle_continues_after_one_player_failure():
    channel = FakeChannel()
    riot = FakeRiotClient()
    riot.by_player["Bad#EUW"] = requests.RequestException("boom")
    riot.by_player["Good#EUW"] = [
        {"queueType": "RANKED_SOLO_5x5", "tier": "SILVER", "rank": "II", "leaguePoints": 20},
    ]
    upserts = []
    logs = []

    asyncio.run(
        process_rank_cycle(
            friends=["Bad#EUW", "Good#EUW"],
            channel=channel,
            riot_client=riot,
            db_load_ranked_state=lambda _riot_id: [],
            db_upsert_ranked_state=lambda riot_id, queue_type, _entry: upserts.append((riot_id, queue_type)),
            db_delete_ranked_state_queue=lambda _riot_id, _queue_type: None,
            log=logs.append,
        )
    )

    assert ("Good#EUW", "RANKED_SOLO_5X5") in upserts
    assert any("Failed rank-check for Bad#EUW" in msg for msg in logs)
