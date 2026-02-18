import os
from zoneinfo import ZoneInfo


def require_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_riot_friends(raw_value):
    friends = [entry.strip() for entry in raw_value.split(",") if entry.strip()]
    if not friends:
        raise RuntimeError("RIOT_FRIENDS cannot be empty.")
    return friends


def normalize_riot_id(raw_riot_id):
    riot_id = raw_riot_id.strip()
    if riot_id.count("#") != 1:
        raise ValueError("Riot ID must be in the format `Name#Tag`.")

    game_name, tag_line = riot_id.split("#", 1)
    game_name = game_name.strip()
    tag_line = tag_line.strip()
    if not game_name or not tag_line:
        raise ValueError("Riot ID must include both name and tag, like `Name#Tag`.")
    return f"{game_name}#{tag_line}"


def get_env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


TOKEN = require_env("DISCORD_TOKEN")
RIOT_API_KEY = require_env("RIOT_API_KEY")
CHANNEL_ID = int(require_env("DISCORD_CHANNEL_ID"))
REPORT_TIMEZONE_NAME = os.getenv("REPORT_TIMEZONE", "UTC")
try:
    REPORT_TIMEZONE = ZoneInfo(REPORT_TIMEZONE_NAME)
except Exception as exc:
    raise RuntimeError(f"Invalid REPORT_TIMEZONE '{REPORT_TIMEZONE_NAME}': {exc}") from exc

LOG_RIOT_REQUESTS = get_env_bool("LOG_RIOT_REQUESTS", False)
LOG_JSON = get_env_bool("LOG_JSON", False)
MAX_MATCHES_PER_PLAYER = int(os.getenv("MAX_MATCHES_PER_PLAYER", "25"))
REPORT_CACHE_SECONDS = int(os.getenv("REPORT_CACHE_SECONDS", "120"))
MAX_TODAY_MATCH_DETAILS = int(os.getenv("MAX_TODAY_MATCH_DETAILS", "20"))
DAILY_REFRESH_SECONDS = int(os.getenv("DAILY_REFRESH_SECONDS", "300"))
MATCH_CACHE_RETENTION_DAYS = int(os.getenv("MATCH_CACHE_RETENTION_DAYS", "31"))
DATABASE_URL = require_env("DATABASE_URL")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))


def get_default_friends():
    return parse_riot_friends(
        os.getenv(
            "RIOT_FRIENDS",
            (
                "NoxVain#EUW,"
                "Tamarin#EUW,"
                "Follow The King#EUW,"
                "Reodor Felgen#EUW,"
                "Not a snake#EUW,"
                "\u00C7\u00DB\u039C\u00CC\u0143\u039C\u00DD\u00C4\u0160\u0160#\u00C3\u00CE\u00D0\u015A,"
                "xXsnakemanXx#EUW,"
                "JonastCvuHU#UNC"
            ),
        )
    )
