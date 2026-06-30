import threading
import requests
import os
import json
from src import config as cfg

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
ITEMS_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/item.json"
SPELLS_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json"
RUNES_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/runesReforged.json"
CHAMPIONS_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"

_CACHE_LOCK = threading.Lock()
_STATIC_CACHE = None

def _fetch_json(url):
    try:
        response = requests.get(url, timeout=(5.05, 10.05))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[static_data] Hiba az adatok letöltésekor: {url} - {e}")
        return None

def get_static_data():
    global _STATIC_CACHE
    with _CACHE_LOCK:
        if _STATIC_CACHE is not None:
            return _STATIC_CACHE

        print("[static_data] Statikus adatok (Hősök, Rúnák, Tárgyak, Spellek) letöltése a Riot CDN-ről...")
        versions = _fetch_json(VERSIONS_URL)
        latest_version = versions[0] if versions else "14.1.1"

        items_raw = _fetch_json(ITEMS_URL.format(version=latest_version))
        item_map = {str(k): v.get("name", "Unknown Item") for k, v in items_raw.get("data", {}).items()} if items_raw else {}

        spells_raw = _fetch_json(SPELLS_URL.format(version=latest_version))
        spell_map = {str(v.get("key")): v.get("name", k) for k, v in spells_raw.get("data", {}).items()} if spells_raw else {}

        runes_raw = _fetch_json(RUNES_URL.format(version=latest_version))
        rune_map = {}
        if runes_raw:
            for tree in runes_raw:
                rune_map[str(tree.get("id"))] = tree.get("name")
                for slot in tree.get("slots", []):
                    for rune in slot.get("runes", []):
                        rune_map[str(rune.get("id"))] = rune.get("name")

        champs_raw = _fetch_json(CHAMPIONS_URL.format(version=latest_version))
        champ_map = {str(k): v.get("name", k) for k, v in champs_raw.get("data", {}).items()} if champs_raw else {}

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        emojis_path = os.path.join(base_dir, "emojis.json")

        emojis_map = {}
        if os.path.exists(emojis_path):
            try:
                with open(emojis_path, "r", encoding="utf-8") as f:
                    emojis_map = json.load(f)
            except Exception as e:
                print(f"[DEBUG-FILE] ❌ KIVÉTEL A FÁJL OLVASÁSAKOR: {e}")

        _STATIC_CACHE = {
            "items": item_map,
            "spells": spell_map,
            "runes": rune_map,
            "champions": champ_map,
            "emojis": emojis_map,
            "version": latest_version
        }

        return _STATIC_CACHE
