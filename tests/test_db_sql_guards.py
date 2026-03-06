import re
from pathlib import Path


def test_player_daily_stats_insert_placeholders_match_columns():
    stats_py = Path("src/db/stats.py").read_text(encoding="utf-8")
    match = re.search(
        r"INSERT INTO player_daily_stats\s*\((?P<cols>.*?)\)\s*"
        r"VALUES\s*\((?P<vals>.*?)\)\s*ON CONFLICT",
        stats_py,
        flags=re.DOTALL,
    )
    assert match is not None, "Could not find player_daily_stats INSERT statement."

    columns = [col.strip() for col in match.group("cols").split(",") if col.strip()]
    values_block = match.group("vals")

    placeholder_count = values_block.count("%s")
    non_generated_columns = [col for col in columns if col != "updated_at"]

    assert "NOW()" in values_block
    assert placeholder_count == len(non_generated_columns)
