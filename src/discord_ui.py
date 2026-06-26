import discord
from src import config as cfg

# --- URL MAPPING ---
LOG_REGION_MAP = {
    "eun1": "eune", "euw1": "euw", "na1": "na", "kr": "kr",
    "la1": "lan", "la2": "las", "oc1": "oce", "tr1": "tr",
    "ru": "ru", "jp1": "jp", "br1": "br", "ph2": "ph",
    "sg2": "sg", "th2": "th", "tw2": "tw", "vn2": "vn"
}

# ⚠️ A DISCORD HACK: Ez a láthatatlan sor garantálja, hogy az Embed mindig maximális szélességű maradjon!
STRETCHER = "\n\u200b" + "\u00A0" * 70 + "\u200b"

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

def format_detailed_scoreboard(participants, friends_puuids, static_data):
    lines = []
    items_map = static_data.get("items", {})
    spells_map = static_data.get("spells", {})
    runes_map = static_data.get("runes", {})

    current_team = None

    for p in participants:
        team_id = p.get("teamId")
        if team_id != current_team:
            current_team = team_id
            if team_id == 100:
                lines.append("🔷 **BLUE TEAM**")
            elif team_id == 200:
                lines.append("♦️ **RED TEAM**")
            else:
                lines.append(f"⚔️ **TEAM {team_id}**")

        name = p.get("riotIdGameName") or p.get("summonerName") or "Unknown"
        is_friend = " 🌟" if p.get("puuid") in friends_puuids else ""

        role = str(p.get("teamPosition", "")).upper()[:3]
        if role == "UTI": role = "SUP"
        if not role or role == "INV": role = "ANY"
        champ = str(p.get("championName", "Unknown"))

        kills, deaths, assists = p.get('kills', 0), p.get('deaths', 0), p.get('assists', 0)
        kda = (kills + assists) / max(1, deaths)
        cs = int(p.get("totalMinionsKilled", 0)) + int(p.get("neutralMinionsKilled", 0))
        gold = f"{int(p.get('goldEarned', 0)/1000)}.{int((p.get('goldEarned', 0)%1000)/100)}k"

        dmg = int(p.get('totalDamageDealtToChampions', 0))
        taken = int(p.get('totalDamageTaken', 0))
        cc = int(p.get('timeCCingOthers', 0))
        vision = int(p.get('visionScore', 0))

        dmg_str = f"{dmg/1000:.1f}k" if dmg >= 1000 else str(dmg)
        taken_str = f"{taken/1000:.1f}k" if taken >= 1000 else str(taken)

        items = []
        for i in range(6):
            item_id = str(p.get(f"item{i}", 0))
            if item_id != "0":
                items.append(items_map.get(item_id, f"Item {item_id}"))
        items_str = ", ".join(items) if items else "No Items"

        spell1 = spells_map.get(str(p.get("summoner1Id")), "Spell1")
        spell2 = spells_map.get(str(p.get("summoner2Id")), "Spell2")

        styles = p.get("perks", {}).get("styles", [])
        primary_rune = "Unknown"
        secondary_tree = "Unknown"
        if len(styles) > 0 and styles[0].get("selections"):
            primary_rune = runes_map.get(str(styles[0]["selections"][0].get("perk")), "Unknown")
        if len(styles) > 1:
            secondary_tree = runes_map.get(str(styles[1].get("style")), "Unknown")

        lines.append(f"> **[{role}] {champ}** ({name}{is_friend})")
        lines.append(f"> ⚔️ `{kills}/{deaths}/{assists}` (KDA: {kda:.1f}) • 🌾 `{cs} CS` • 💰 `{gold} Gold`")
        lines.append(f"> 💥 `{dmg_str} Dmg` • 🛡️ `{taken_str} Taken` • 🪄 `{cc} CC` • 👁️ `{vision} VS`")
        lines.append(f"> ✨ {spell1} & {spell2} • 🔮 {primary_rune} & {secondary_tree}")
        lines.append(f"> 🎒 {items_str}")
        lines.append("")

    return "\n".join(lines) + STRETCHER

def format_graph_text(participants, friends_puuids, data_sets, title):
    lines = [f"**📊 {title.upper()}**\n"]

    primary_key = data_sets[0][0]
    max_val = max((int(p.get(primary_key, 0) or 0) for p in participants), default=1)
    if max_val == 0: max_val = 1

    sorted_participants = sorted(participants, key=lambda p: 0 if p.get("puuid") in friends_puuids else 1)

    for p in sorted_participants:
        champ = str(p.get("championName", "Unknown"))
        champ_trunc = (champ[:9] + ".").ljust(10) if len(champ) > 10 else champ.ljust(10)

        is_friend = " 🌟" if p.get("puuid") in friends_puuids else ""

        primary_val = int(p.get(primary_key, 0) or 0)
        percentage = primary_val / max_val
        bar = generate_emoji_bar(percentage, length=10) # 10 hosszú csík

        val_str = f"{primary_val/1000:.1f}k".rjust(6) if primary_val >= 1000 else str(primary_val).rjust(6)

        lines.append(f"**{champ}**{is_friend} | **{val_str}**")
        lines.append(f"{bar}")

        if len(data_sets) > 1:
            details = []
            for stat_key, emoji, label in data_sets[1:]:
                val = int(p.get(stat_key, 0) or 0)
                val_formatted = f"{val/1000:.1f}k" if val >= 1000 else str(val)
                details.append(f"{emoji} {label}:\u00A0`{val_formatted}`")
            lines.append(f"> {' • '.join(details)}")
        lines.append("")

    return "\n".join(lines) + STRETCHER


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

    async def update_state(self, interaction, clicked_button, content_text):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.url is None:
                if child == clicked_button:
                    child.style = discord.ButtonStyle.primary
                else:
                    child.style = discord.ButtonStyle.secondary

        if len(content_text) > 4000:
            content_text = content_text[:4000] + "\n...[Content truncated due to length]"

        embed = interaction.message.embeds[0]
        embed.description = content_text
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Scoreboard", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def btn_scoreboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = format_detailed_scoreboard(self.match_data["participants"], self.friends_puuids, self.static_data)
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.secondary, emoji="💥", row=0)
    async def btn_damage(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [
            ("totalDamageDealtToChampions", "💥", "Total"),
            ("physicalDamageDealtToChampions", "⚔️", "Phys"),
            ("magicDamageDealtToChampions", "🪄", "Magic"),
            ("trueDamageDealtToChampions", "🩸", "True")
        ]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Damage Dealt")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Taken", style=discord.ButtonStyle.secondary, emoji="🛡️", row=0)
    async def btn_taken(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [
            ("totalDamageTaken", "🛡️", "Total"),
            ("physicalDamageTaken", "⚔️", "Phys"),
            ("magicDamageTaken", "🪄", "Magic"),
            ("trueDamageTaken", "🩸", "True")
        ]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Damage Taken")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Mitigated", style=discord.ButtonStyle.secondary, emoji="🧱", row=0)
    async def btn_mitigated(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("damageSelfMitigated", "🧱", "Mitigated")]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Self Mitigated Damage")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Healing", style=discord.ButtonStyle.secondary, emoji="💚", row=0)
    async def btn_heal(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("totalHeal", "💚", "Healing")]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Healing Done")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="CC", style=discord.ButtonStyle.secondary, emoji="🪄", row=1)
    async def btn_cc(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("timeCCingOthers", "🪄", "CC Score")]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Crowd Control")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Vision", style=discord.ButtonStyle.secondary, emoji="👁️", row=1)
    async def btn_vision(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [
            ("visionScore", "👁️", "Score"),
            ("wardsPlaced", "📍", "Placed"),
            ("wardsKilled", "❌", "Cleared")
        ]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Vision & Wards")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Turrets", style=discord.ButtonStyle.secondary, emoji="🗼", row=1)
    async def btn_turrets(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("damageDealtToTurrets", "🗼", "Damage")]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Damage to Turrets")
        await self.update_state(interaction, button, text)

    @discord.ui.button(label="Objectives", style=discord.ButtonStyle.secondary, emoji="🐉", row=1)
    async def btn_obj(self, interaction: discord.Interaction, button: discord.ui.Button):
        data_sets = [("damageDealtToObjectives", "🐉", "Damage")]
        text = format_graph_text(self.match_data["participants"], self.friends_puuids, data_sets, "Damage to Objectives")
        await self.update_state(interaction, button, text)
