import requests

from src.riot_api import RiotApiClient


class DummyResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


def build_client():
    return RiotApiClient(
        riot_api_key="test-key",
        riot_platform_routing="euw1",
        log=lambda _msg: None,
        log_riot_requests=False,
        report_timezone=None,
        report_day_start_hour=6,
        max_today_match_details=20,
        max_match_ids_scan=2000,
        max_in_memory_match_cache=200,
        db_get_puuid=lambda _riot_id: None,
        db_upsert_player=lambda _riot_id, _puuid: None,
        db_get_match_info=lambda _match_id: None,
        db_upsert_match_info=lambda _match_id, _match_info: None,
        db_set_last_seen_match_id=lambda _riot_id, _match_id: None,
    )


def test_riot_get_json_retries_on_transient_http(monkeypatch):
    client = build_client()
    sequence = [
        DummyResponse(503),
        DummyResponse(200, payload={"ok": True}),
    ]
    calls = {"count": 0}

    def fake_get(_url, headers=None, timeout=20):
        _ = headers, timeout
        item = sequence[calls["count"]]
        calls["count"] += 1
        return item

    monkeypatch.setattr("src.riot_api.requests.get", fake_get)
    monkeypatch.setattr("src.riot_api.time.sleep", lambda _secs: None)
    monkeypatch.setattr("src.riot_api.random.uniform", lambda _a, _b: 0.0)

    result = client.riot_get_json("https://example.test")
    assert result == {"ok": True}
    assert calls["count"] == 2


def test_riot_get_json_retries_on_request_exception(monkeypatch):
    client = build_client()
    calls = {"count": 0}

    def fake_get(_url, headers=None, timeout=20):
        _ = headers, timeout
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.Timeout("timeout")
        return DummyResponse(200, payload={"ok": True})

    monkeypatch.setattr("src.riot_api.requests.get", fake_get)
    monkeypatch.setattr("src.riot_api.time.sleep", lambda _secs: None)
    monkeypatch.setattr("src.riot_api.random.uniform", lambda _a, _b: 0.0)

    result = client.riot_get_json("https://example.test")
    assert result == {"ok": True}
    assert calls["count"] == 2
