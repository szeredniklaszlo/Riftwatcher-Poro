import math
import time


def get_mode_bucket(queue_id):
    if queue_id == 420:
        return "solo_duo"
    if queue_id == 440:
        return "flex"
    return "arcade"


def create_mode_records():
    return {
        "solo_duo": {"wins": 0, "losses": 0},
        "flex": {"wins": 0, "losses": 0},
        "arcade": {"wins": 0, "losses": 0},
    }


def get_mode_totals(mode_records):
    wins = sum(bucket["wins"] for bucket in mode_records.values())
    losses = sum(bucket["losses"] for bucket in mode_records.values())
    return wins, losses


def wilson_lower_bound(wins, losses, z=1.28):
    n = wins + losses
    if n <= 0:
        return 0.0
    p = wins / n
    z2 = z * z
    denominator = 1 + (z2 / n)
    center = p + (z2 / (2 * n))
    margin = z * math.sqrt((p * (1 - p) + (z2 / (4 * n))) / n)
    return (center - margin) / denominator


def rank_sort_key(row):
    wins = row[2]
    losses = row[3]
    win_rate = row[4]
    return (-wilson_lower_bound(wins, losses), -win_rate, -(wins + losses), row[0].lower())


def format_mode_line(label, wins, losses):
    total = wins + losses
    if total == 0:
        return f"   {label}: `0W-0L` - **N/A**"
    win_rate = (wins / total) * 100
    return f"   {label}: `{wins}W-{losses}L` - **{win_rate:.1f}%**"


def get_match_end_unix_seconds(match_info):
    end_ms = match_info["info"].get("gameEndTimestamp")
    if not end_ms:
        creation_ms = match_info["info"].get("gameCreation", 0)
        duration_s = match_info["info"].get("gameDuration", 0)
        end_ms = creation_ms + (duration_s * 1000)
    return int(end_ms / 1000)


def is_match_in_last_24h(match_info, now_ts=None):
    if now_ts is None:
        now_ts = int(time.time())
    window_start = now_ts - (24 * 60 * 60)
    end_ts = get_match_end_unix_seconds(match_info)
    return end_ts >= window_start
