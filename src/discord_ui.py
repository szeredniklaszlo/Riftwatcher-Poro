import discord
from src import config as cfg

LOG_REGION_MAP = {
    "eun1": "eune", "euw1": "euw", "na1": "na", "kr": "kr",
    "la1": "lan", "la2": "las", "oc1": "oce", "tr1": "tr",
    "ru": "ru", "jp1": "jp", "br1": "br", "ph2": "ph",
    "sg2": "sg", "th2": "th", "tw2": "tw", "vn2": "vn"
}

def generate_emoji_bar(percentage, length=10):
    filled_length = int(round(percentage * length))
    bar = ""
    for i in range(length):
        if i == 0:
            bar += cfg.BAR_LEFT_FULL if filled_length > i else cfg.BAR_LEFT_EMPTY
        elif i == length - 1:
            bar += cfg.BAR_RIGHT_FULL if filled_length > i else cfg.BAR_RIGHT_EMPTY
        else:
            bar += cfg.BAR_MID_FULL if filled_length > i else cfg.BAR_MID_EMPTY
    return bar

def get_emo(emojis_dict, raw_id, prefix=""):
    if not emojis_dict:
        return None
    return emojis_dict.get(raw_id, emojis_dict.get(f"{prefix}{raw_id}"))

def apply_player_summary_fields(embed, primary_p, tier_str, static_data, timeline_data):
    emojis = static_data.get("emojis", {})
    runes_map = static_data.get("runes", {})
    spells_map = static_data.get("spells", {})

    role_key = str(primary_p.get("teamPosition", "")).lower()
    if not role_key or role_key == "inv": role_key = "any"

    role_emoji = get_emo(emojis, role_key, "role_") or "⚔️"
    role_name = role_key.capitalize() if role_key else "Any"

    tier_key = tier_str.split()[0].lower() if tier_str else "unranked"
    rank_emoji = get_emo(emojis, tier_key, "rank_") or "🏅"

    spell1_id = str(primary_p.get('summoner1Id'))
    spell2_id = str(primary_p.get('summoner2Id'))
    spell1_emo = get_emo(emojis, spell1_id, "spell_") or "✨"
    spell2_emo = get_emo(emojis, spell2_id, "spell_") or "✨"
    spell1_name = spells_map.get(spell1_id, "Spell 1")
    spell2_name = spells_map.get(spell2_id, "Spell 2")

    embed.add_field(name=f"{rank_emoji} {tier_str.title()}", value=f"{role_emoji} **{role_name}**", inline=True)
    embed.add_field(name="Summoner Spells", value=f"{spell1_emo} {spell1_name}\n{spell2_emo} {spell2_name}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    styles = primary_p.get("perks", {}).get("styles", [])
    primary_str = "Unknown"
    secondary_str = "Unknown"

    if len(styles) > 0:
        p_tree = str(styles[0].get("style"))
        p_tree_name = runes_map.get(p_tree, "Primary")
        p_tree_emoji = get_emo(emojis, p_tree, "rune_") or "🔮"

        p_runes = []
        for sel in styles[0].get("selections", []):
            r_id = str(sel.get("perk"))
            r_emo = get_emo(emojis, r_id, "rune_") or "🔹"
            p_runes.append(f"{r_emo} {runes_map.get(r_id, 'Rune')}")
        primary_str = f"{p_tree_emoji} **__({p_tree_name})__**\n\n" + "\n".join(p_runes)

    if len(styles) > 1:
        s_tree = str(styles[1].get("style"))
        s_tree_name = runes_map.get(s_tree, "Secondary")
        s_tree_emoji = get_emo(emojis, s_tree, "rune_") or "🔮"

        s_runes = []
        for sel in styles[1].get("selections", []):
            r_id = str(sel.get("perk"))
            r_emo = get_emo(emojis, r_id, "rune_") or "🔸"
            s_runes.append(f"{r_emo} {runes_map.get(r_id, 'Rune')}")
        secondary_str = f"{s_tree_emoji} **__({s_tree_name})__**\n\n" + "\n".join(s_runes)

    embed.add_field(name="Primary Rune", value=primary_str, inline=True)
    embed.add_field(name="Secondary Rune", value=secondary_str, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    participant_id = primary_p.get("participantId")
    purchases = []
    IGNORE_ITEMS = {"2003", "2010", "2055", "3340", "3364", "3330", "3363"}

    if timeline_data and "info" in timeline_data and participant_id:
        for frame in timeline_data["info"].get("frames", []):
            for event in frame.get("events", []):
                if event.get("participantId") == participant_id:
                    item_id = str(event.get("itemId", ""))
                    if event.get("type") == "ITEM_PURCHASED" and item_id not in IGNORE_ITEMS:
                        purchases.append(item_id)
                    elif event.get("type") == "ITEM_UNDO":
                        undo_id = str(event.get("beforeId", ""))
                        if undo_id in purchases:
                            purchases.reverse()
                            purchases.remove(undo_id)
                            purchases.reverse()

    item_emojis = []
    for i in purchases:
        emo = get_emo(emojis, i, "item_")
        if emo: item_emojis.append(emo)
        else: item_emojis.append(f"*{i}*")

    if not item_emojis:
        for i in range(6):
            itm = str(primary_p.get(f"item{i}", 0))
            if itm != "0" and itm not in IGNORE_ITEMS:
                emo = get_emo(emojis, itm, "item_")
                item_emojis.append(emo if emo else f"*{itm}*")

    item_path = " > ".join(item_emojis[:25]) if item_emojis else "No items purchased."
    embed.add_field(name="Item Build Path", value=item_path, inline=False)


# --- OSZLOPOS NÉZETEK LOGIKÁJA ---

def get_sorted_teams(participants):
    teams = {}
    for p in participants:
        t_id = p.get("teamId", 0)
        if t_id not in teams:
            teams[t_id] = []
        teams[t_id].append(p)

    role_order = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
    for t_id in teams:
        teams[t_id].sort(key=lambda p: role_order.get(str(p.get("teamPosition", "")).upper(), 99))

    sorted_teams = sorted(teams.values(), key=len, reverse=True)
    team_1 = sorted_teams[0] if len(sorted_teams) > 0 else []
    team_2 = sorted_teams[1] if len(sorted_teams) > 1 else []

    return team_1, team_2

def generate_scoreboard_field(p, friends_puuids, static_data):
    emojis = static_data.get("emojis", {})
    name = p.get("riotIdGameName") or p.get("summonerName") or "Unknown"
    is_friend = "🌟" if p.get("puuid") in friends_puuids else ""

    role_key = str(p.get("teamPosition", "")).lower()
    if not role_key or role_key == "inv": role_key = "any"
    role_emoji = get_emo(emojis, role_key, "role_") or ""

    raw_champ = str(p.get("championName", "Unknown"))
    champ_emoji = get_emo(emojis, raw_champ, "champ_") or ""

    kills, deaths, assists = p.get('kills', 0), p.get('deaths', 0), p.get('assists', 0)
    kda = (kills + assists) / max(1, deaths)
    cs = int(p.get("totalMinionsKilled", 0)) + int(p.get("neutralMinionsKilled", 0))
    gold = f"{int(p.get('goldEarned', 0)/1000)}.{int((p.get('goldEarned', 0)%1000)/100)}k"
    dmg = int(p.get('totalDamageDealtToChampions', 0))
    dmg_str = f"{dmg/1000:.1f}k" if dmg >= 1000 else str(dmg)
    vision = int(p.get('visionScore', 0))

    title = f"{role_emoji} {champ_emoji} **{name}** {is_friend}"
    value = (
        f"⚔️ `{kills}/{deaths}/{assists}` ({kda:.1f})\n"
        f"🌾 `{cs} CS` • 💰 `{gold}`\n"
        f"💥 `{dmg_str}` • 👁️ `{vision}`"
    )
    return title, value

def generate_builds_field(p, friends_puuids, static_data):
    emojis = static_data.get("emojis", {})
    name = p.get("riotIdGameName") or p.get("summonerName") or "Unknown"
    is_friend = "🌟" if p.get("puuid") in friends_puuids else ""

    role_key = str(p.get("teamPosition", "")).lower()
    if not role_key or role_key == "inv": role_key = "any"
    role_emoji = get_emo(emojis, role_key, "role_") or ""

    raw_champ = str(p.get("championName", "Unknown"))
    champ_emoji = get_emo(emojis, raw_champ, "champ_") or ""

    items = []
    for i in range(7):
        item_id = str(p.get(f"item{i}", 0))
        if item_id != "0":
            emo = get_emo(emojis, item_id, "item_")
            if emo: items.append(emo)
    items_str = "".join(items) if items else "No Items"

    spell1_id = str(p.get("summoner1Id"))
    spell2_id = str(p.get("summoner2Id"))
    spell1_emo = get_emo(emojis, spell1_id, "spell_") or "✨"
    spell2_emo = get_emo(emojis, spell2_id, "spell_") or "✨"

    styles = p.get("perks", {}).get("styles", [])
    primary_rune_emo = "🔮"
    secondary_tree_emo = "🔮"
    if len(styles) > 0 and styles[0].get("selections"):
        r_id = str(styles[0]["selections"][0].get("perk"))
        primary_rune_emo = get_emo(emojis, r_id, "rune_") or "🔮"
    if len(styles) > 1:
        t_id = str(styles[1].get("style"))
        secondary_tree_emo = get_emo(emojis, t_id, "rune_") or "🔮"

    title = f"{role_emoji} {champ_emoji} **{name}** {is_friend}"
    value = (
        f"{spell1_emo}{spell2_emo} • {primary_rune_emo} & {secondary_tree_emo}\n"
        f"🎒 {items_str}"
    )
    return title, value

def apply_side_by_side_layout(embed, participants, friends_puuids, static_data, generator_func):
    team_1, team_2 = get_sorted_teams(participants)

    if not team_2:
        for p in team_1:
            n, v = generator_func(p, friends_puuids, static_data)
            embed.add_field(name=n, value=v, inline=False)
        return

    embed.add_field(name="🔷 **BLUE TEAM**", value="\u200b", inline=True)
    embed.add_field(name="♦️ **RED TEAM**", value="\u200b", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    for i in range(max(len(team_1), len(team_2))):
        p_blue = team_1[i] if i < len(team_1) else None
        p_red = team_2[i] if i < len(team_2) else None

        if p_blue:
            n, v = generator_func(p_blue, friends_puuids, static_data)
            embed.add_field(name=n, value=v, inline=True)
        else:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        if p_red:
            n, v = generator_func(p_red, friends_puuids, static_data)
            embed.add_field(name=n, value=v, inline=True)
        else:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=True)


# --- GRAFIKUS NÉZETEK LOGIKÁJA ---

def format_graph_text(participants, friends_puuids, data_sets, title, static_data, bar_length=10):
    emojis = static_data.get("emojis", {})
    lines = [f"**📊 {title.upper()}**\n"]

    primary_key = data_sets[0][0]
    max_val = max((int(p.get(primary_key, 0) or 0) for p in participants), default=1)
    if max_val == 0: max_val = 1

    sorted_participants = sorted(participants, key=lambda p: 0 if p.get("puuid") in friends_puuids else 1)

    for p in sorted_participants:
        raw_champ = str(p.get("championName", "Unknown"))
        champ_emoji = get_emo(emojis, raw_champ, "champ_") or ""
        name = p.get("riotIdGameName") or p.get("summonerName") or "Unknown"
        is_friend = " 🌟" if p.get("puuid") in friends_puuids else ""

        primary_val = int(p.get(primary_key, 0) or 0)
        percentage = primary_val / max_val
        bar = generate_emoji_bar(percentage, length=bar_length)

        val_str = f"{primary_val/1000:.1f}k".rjust(6) if primary_val >= 1000 else str(primary_val).rjust(6)

        lines.append(f"{champ_emoji} **{name}**{is_friend} | **{val_str}**")
        lines.append(f"{bar}")

        if len(data_sets) > 1:
            details = []
            for stat_key, custom_emo_name, fallback_emo, label in data_sets[1:]:
                val = int(p.get(stat_key, 0) or 0)
                val_formatted = f"{val/1000:.1f}k" if val >= 1000 else str(val)
                emo = get_emo(emojis, custom_emo_name) or fallback_emo
                details.append(f"{emo} {label}:\u00A0`{val_formatted}`")
            lines.append(f"> {' • '.join(details)}")

        lines.append("")

    return "\n".join(lines).strip()


# --- DISCORD UI VIEW ---

class MatchRecapView(discord.ui.View):
    def __init__(self, match_data, friends_puuids, static_data):
        super().__init__(timeout=None)
        self.match_data = match_data
        self.friends_puuids = friends_puuids
        self.static_data = static_data

        match_id = match_data["match_id"]
        region_raw, match_num = match_id.split("_")
        region_raw = region_raw.lower()

        log_region = LOG_REGION_MAP.get(region_raw, region_raw)
        log_url = f"https://www.leagueofgraphs.com/match/{log_region}/{match_num}"

        full_riot_id = match_data["primary_friend_riot_id"]
        ugg_riot_id = full_riot_id.replace("#", "-").lower()
        ugg_url = f"https://u.gg/lol/profile/{region_raw}/{ugg_riot_id}/overview"

        self.add_item(discord.ui.Button(label="LeagueOfGraphs", url=log_url, row=2))
        self.add_item(discord.ui.Button(label="U.GG Profile", url=ugg_url, row=2))

        # --- DINAMIKUS EMOJI A GOMBON ---
        # Lekérjük a Hős Emojit, majd beállítjuk a Champion Info gombra
        raw_champ = str(match_data["primary_p"].get("championName", "Unknown"))
        champ_emoji_str = get_emo(static_data.get("emojis", {}), raw_champ, "champ_")

        if champ_emoji_str and champ_emoji_str.startswith("<:"):
            try:
                # String darabolása, pl: "<:champ_Ahri:123456789>" -> név: champ_Ahri, id: 123456789
                parts = champ_emoji_str.strip("<>").split(":")
                if len(parts) == 3:
                    champ_emoji_obj = discord.PartialEmoji(name=parts[1], id=int(parts[2]))
                    # Megkeressük a "Champion Info" gombot a Children listában
                    for child in self.children:
                        if getattr(child, "label", "") == "Champion Info":
                            child.emoji = champ_emoji_obj
                            break
            except Exception:
                pass


    async def update_state(self, interaction, clicked_button):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.url is None:
                if child == clicked_button:
                    child.style = discord.ButtonStyle.primary
                else:
                    child.style = discord.ButtonStyle.secondary

        embed = interaction.message.embeds[0]
        await interaction.response.edit_message(embed=embed, view=self)

    # --- ÁLLAPOT VÁLTÓ FÜGGVÉNYEK ---

    def apply_scoreboard(self, embed):
        embed.clear_fields()
        embed.description = None
        if self.match_data["splash_url"]:
            embed.set_image(url=self.match_data["splash_url"])
        apply_side_by_side_layout(embed, self.match_data["participants"], self.friends_puuids, self.static_data, generate_scoreboard_field)

    def apply_builds(self, embed):
        embed.clear_fields()
        embed.description = None
        if self.match_data["splash_url"]:
            embed.set_image(url=self.match_data["splash_url"])
        apply_side_by_side_layout(embed, self.match_data["participants"], self.friends_puuids, self.static_data, generate_builds_field)

    def apply_player_summary(self, embed):
        embed.clear_fields()
        embed.description = None
        if self.match_data["splash_url"]:
            embed.set_image(url=self.match_data["splash_url"])
        apply_player_summary_fields(embed, self.match_data["primary_p"], self.match_data["tier_str"], self.static_data, self.match_data["timeline_data"])

    def apply_graph(self, embed, data_sets, title, bar_length=10):
        embed.clear_fields()
        embed.set_image(url=None)
        embed.description = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, title, self.static_data, bar_length)

    # --- GOMBOK ---

    @discord.ui.button(label="Scoreboard", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def btn_scoreboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.apply_scoreboard(interaction.message.embeds[0])
        await self.update_state(interaction, button)

    @discord.ui.button(label="Builds & Runes", style=discord.ButtonStyle.secondary, emoji="🎒", row=0)
    async def btn_builds(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.apply_builds(interaction.message.embeds[0])
        await self.update_state(interaction, button)

    @discord.ui.button(label="Champion Info", style=discord.ButtonStyle.secondary, emoji="👤", row=0)
    async def btn_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.apply_player_summary(interaction.message.embeds[0])
        await self.update_state(interaction, button)

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.secondary, emoji="💥", row=1)
    async def btn_damage(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [
            ("totalDamageDealtToChampions", "stat_total_dmg", "💥", "Total"),
            ("physicalDamageDealtToChampions", "stat_ad", "⚔️", "Phys"),
            ("magicDamageDealtToChampions", "stat_ap", "🪄", "Magic"),
            ("trueDamageDealtToChampions", "stat_true", "🩸", "True")
        ]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Damage Dealt", bar_length=8)
        await self.update_state(interaction, button)

    @discord.ui.button(label="Taken", style=discord.ButtonStyle.secondary, emoji="🛡️", row=1)
    async def btn_taken(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [
            ("totalDamageTaken", "stat_total_taken", "🛡️", "Total"),
            ("physicalDamageTaken", "stat_ad", "⚔️", "Phys"),
            ("magicDamageTaken", "stat_ap", "🪄", "Magic"),
            ("trueDamageTaken", "stat_true", "🩸", "True")
        ]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Damage Taken", bar_length=8)
        await self.update_state(interaction, button)

    @discord.ui.button(label="Mitigated", style=discord.ButtonStyle.secondary, emoji="🧱", row=1)
    async def btn_mitigated(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("damageSelfMitigated", "stat_mitigated", "🧱", "Mitigated")]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Self Mitigated Damage")
        await self.update_state(interaction, button)

    @discord.ui.button(label="Turrets", style=discord.ButtonStyle.secondary, emoji="🗼", row=1)
    async def btn_turrets(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("damageDealtToTurrets", "stat_turret", "🗼", "Damage")]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Damage to Turrets")
        await self.update_state(interaction, button)

    @discord.ui.button(label="Objectives", style=discord.ButtonStyle.secondary, emoji="🐉", row=1)
    async def btn_obj(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("damageDealtToObjectives", "stat_objective", "🐉", "Damage")]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Damage to Objectives")
        await self.update_state(interaction, button)

    @discord.ui.button(label="Healing", style=discord.ButtonStyle.secondary, emoji="💚", row=2)
    async def btn_heal(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("totalHeal", "stat_heal", "💚", "Healing")]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Healing Done")
        await self.update_state(interaction, button)

    @discord.ui.button(label="CC", style=discord.ButtonStyle.secondary, emoji="🪄", row=2)
    async def btn_cc(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("timeCCingOthers", "stat_cc", "🪄", "CC Score")]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Crowd Control")
        await self.update_state(interaction, button)

    @discord.ui.button(label="Vision", style=discord.ButtonStyle.secondary, emoji="👁️", row=2)
    async def btn_vision(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [
            ("visionScore", "stat_vision", "👁️", "Score"),
            ("wardsPlaced", "stat_ward_placed", "📍", "Placed"),
            ("wardsKilled", "stat_ward_killed", "❌", "Cleared")
        ]
        self.apply_graph(interaction.message.embeds[0], data_sets, "Vision & Wards", bar_length=9)
        await self.update_state(interaction, button)
