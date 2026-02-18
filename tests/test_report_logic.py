from src.report_logic import (
    format_mode_line,
    get_match_end_unix_seconds,
    get_mode_bucket,
    is_match_in_last_24h,
    rank_sort_key,
    wilson_lower_bound,
)


def test_get_mode_bucket_maps_ranked_and_arcade():
    assert get_mode_bucket(420) == "solo_duo"
    assert get_mode_bucket(440) == "flex"
    assert get_mode_bucket(450) == "arcade"
    assert get_mode_bucket(1700) == "arcade"


def test_wilson_lower_bound_prefers_consistent_sample():
    strong_large_sample = wilson_lower_bound(9, 1)
    perfect_tiny_sample = wilson_lower_bound(1, 0)
    assert strong_large_sample > perfect_tiny_sample


def test_rank_sort_key_orders_by_wilson_then_volume():
    rows = [
        ("OneGame", {}, 1, 0, 100.0),
        ("Solid", {}, 9, 1, 90.0),
        ("Mid", {}, 5, 5, 50.0),
    ]
    ranked = sorted(rows, key=rank_sort_key)
    assert [row[0] for row in ranked] == ["Solid", "OneGame", "Mid"]


def test_format_mode_line_handles_empty_and_non_empty():
    assert format_mode_line("Arcade", 0, 0) == "   Arcade: `0W-0L` - **N/A**"
    assert format_mode_line("Arcade", 3, 1) == "   Arcade: `3W-1L` - **75.0%**"


def test_get_match_end_unix_seconds_falls_back_when_end_timestamp_missing():
    match_info = {"info": {"gameCreation": 1_000_000, "gameDuration": 120}}
    assert get_match_end_unix_seconds(match_info) == 1120


def test_is_match_in_last_24h_uses_game_end_timestamp():
    now_ts = 2_000_000
    recent_match = {"info": {"gameEndTimestamp": (now_ts - 60) * 1000}}
    old_match = {"info": {"gameEndTimestamp": (now_ts - (24 * 60 * 60) - 1) * 1000}}

    assert is_match_in_last_24h(recent_match, now_ts=now_ts)
    assert not is_match_in_last_24h(old_match, now_ts=now_ts)
