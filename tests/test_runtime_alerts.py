import asyncio

from src.runtime.alerts import (
    RiotAlertState,
    check_and_notify_worker_stalls,
    mark_riot_401_alert_sent,
    riot_401_alert_already_sent,
    send_riot_key_expired_alert,
    trigger_riot_key_alert,
)


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


def test_riot_401_alert_already_sent_uses_memory_and_db_state():
    state = RiotAlertState()
    db = {"riot_401_alert_sent": "0"}

    assert riot_401_alert_already_sent(state=state, db_get_state=lambda key: db.get(key)) is False

    mark_riot_401_alert_sent(state=state, db_set_state=lambda key, value: db.update({key: value}))
    assert state.riot_401_alert_sent is True
    assert db["riot_401_alert_sent"] == "1"
    assert riot_401_alert_already_sent(state=state, db_get_state=lambda key: db.get(key)) is True


def test_riot_401_alert_already_sent_reads_persisted_flag():
    state = RiotAlertState()

    assert riot_401_alert_already_sent(state=state, db_get_state=lambda _key: "1") is True
    assert state.riot_401_alert_sent is True


def test_send_riot_key_expired_alert_posts_to_events_channel():
    channel = FakeChannel()
    logs = []

    async def resolve_channel(_channel_id):
        return channel

    asyncio.run(
        send_riot_key_expired_alert(
            resolve_channel=resolve_channel,
            events_channel_id=123,
            log=logs.append,
        )
    )

    assert len(channel.sent) == 1
    assert "401 Unauthorized" in channel.sent[0]
    assert any("expiry alert" in entry for entry in logs)


def test_trigger_riot_key_alert_marks_only_after_success(monkeypatch):
    db = {}
    logs = []

    class FakeClient:
        def __init__(self, loop):
            self.loop = loop

    class FakeFuture:
        pass

    def fake_run_coroutine_threadsafe(coro, loop):
        loop.create_task(coro)
        return FakeFuture()

    monkeypatch.setattr("src.runtime.alerts.asyncio.run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    async def scenario():
        state = RiotAlertState()
        channel = FakeChannel()
        client = FakeClient(asyncio.get_running_loop())
        async def resolve_channel(_channel_id):
            return channel
        trigger_riot_key_alert(
            state=state,
            client=client,
            resolve_channel=resolve_channel,
            events_channel_id=123,
            db_get_state=lambda key: db.get(key),
            db_set_state=lambda key, value: db.update({key: value}),
            log=logs.append,
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert state.riot_401_alert_sent is True
        assert db.get("riot_401_alert_sent") == "1"

    asyncio.run(scenario())


def test_trigger_riot_key_alert_does_not_mark_when_send_fails(monkeypatch):
    db = {}
    logs = []

    class FakeClient:
        def __init__(self, loop):
            self.loop = loop

    class FakeFuture:
        pass

    class FailingChannel:
        async def send(self, _content):
            raise RuntimeError("send failed")

    def fake_run_coroutine_threadsafe(coro, loop):
        loop.create_task(coro)
        return FakeFuture()

    monkeypatch.setattr("src.runtime.alerts.asyncio.run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    async def scenario():
        state = RiotAlertState()
        client = FakeClient(asyncio.get_running_loop())
        async def resolve_channel(_channel_id):
            return FailingChannel()
        trigger_riot_key_alert(
            state=state,
            client=client,
            resolve_channel=resolve_channel,
            events_channel_id=123,
            db_get_state=lambda key: db.get(key),
            db_set_state=lambda key, value: db.update({key: value}),
            log=logs.append,
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert state.riot_401_alert_sent is False
        assert db.get("riot_401_alert_sent") is None
        assert any("Failed to send" in entry for entry in logs)

    asyncio.run(scenario())


def test_check_and_notify_worker_stalls_sends_stale_and_recovery_messages():
    channel = FakeChannel()
    logs = []
    state = {"alerted_by_worker": {}}
    db = {}

    async def resolve_channel(_channel_id):
        return channel

    worker_stats = {
        "refresh": {"runs": 3, "last_success_at": 10.0},
    }
    thresholds = {"refresh": 30}

    asyncio.run(
        check_and_notify_worker_stalls(
            state=state,
            resolve_channel=resolve_channel,
            events_channel_id=123,
            worker_stats=worker_stats,
            stale_thresholds_seconds=thresholds,
            db_get_state=lambda key: db.get(key),
            db_set_state=lambda key, value: db.update({key: value}),
            now_monotonic=50.0,
            log=logs.append,
        )
    )

    assert len(channel.sent) == 1
    assert "appears stalled" in channel.sent[0]
    assert state["alerted_by_worker"]["refresh"] is True
    assert db["worker_stall_alert_sent::refresh"] == "1"

    # same stale condition should not spam duplicate alerts
    asyncio.run(
        check_and_notify_worker_stalls(
            state=state,
            resolve_channel=resolve_channel,
            events_channel_id=123,
            worker_stats=worker_stats,
            stale_thresholds_seconds=thresholds,
            db_get_state=lambda key: db.get(key),
            db_set_state=lambda key, value: db.update({key: value}),
            now_monotonic=55.0,
            log=logs.append,
        )
    )
    assert len(channel.sent) == 1

    # recovery clears alert and sends one recovery message
    worker_stats["refresh"]["last_success_at"] = 54.0
    asyncio.run(
        check_and_notify_worker_stalls(
            state=state,
            resolve_channel=resolve_channel,
            events_channel_id=123,
            worker_stats=worker_stats,
            stale_thresholds_seconds=thresholds,
            db_get_state=lambda key: db.get(key),
            db_set_state=lambda key, value: db.update({key: value}),
            now_monotonic=60.0,
            log=logs.append,
        )
    )
    assert len(channel.sent) == 2
    assert "recovered" in channel.sent[1]
    assert state["alerted_by_worker"]["refresh"] is False
    assert db["worker_stall_alert_sent::refresh"] == "0"
