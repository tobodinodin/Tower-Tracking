import os
import csv
import json
import discord
import requests
import logging
import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
from discord import app_commands
from discord.ext import commands

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger('TowerBot')

# Config - Replace these with your actual keys
DISC_TOKEN = 'Token'
TOWERSTATS_KEY = 'API'
DISC_ID = 1282662864586543157 # Use your actual discord ID
DB_FILE = "leaderboard.json"
MAINTENANCE_MODE = False

EMOJIS = {
    8: "<:Insane:1463889989333942416>", 9: "<:Extreme:1463890005163511842>",
    10: "<:Terrifying:1463890036318671003>", 11: "<:Catastrophic:1463890064978477176>",
    12: "<:Horrific:1463890091297472545>", 13: "<:Unreal:1463890107244482721>"
}

def load_leaderboard():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        try:
            return json.load(f)
        except (json.JSONDecodeError, EOFError):
            return {}

def save_to_leaderboard(username, xp):
    data = load_leaderboard()
    data[username] = xp
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def calculate_xp(diff):
    if diff < 8.0 or diff >= 14.0: return 0
    base = {8: 1500, 9: 2500, 10: 4000, 11: 8000, 12: 15000, 13: 25000}.get(int(diff), 0)
    return base + int((diff - int(diff)) * 250)

tower_data = {}
csv_loaded = False

# Load CSV Data
try:
    if os.path.exists('towers.csv'):
        with open('towers.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bid = int(float(row['badge_id']))
                tower_data[bid] = {
                    "name": row['name'],
                    "difficulty": float(row['difficulty'].replace('*', '').replace('!', '')),
                    "is_tracked": str(row['is_tracked']).strip().lower() == "true"
                }
        csv_loaded = True
    else:
        logger.error("towers.csv not found!")
except Exception as e:
    logger.error(f"Err 1802: {e}")

class TowerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.check_lock = asyncio.Lock()

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Slash commands synced.")

bot = TowerBot()

@bot.tree.command(name="maintenance", description="Toggle maintenance (Dev Only)")
async def maintenance(interaction: discord.Interaction, status: bool):
    if interaction.user.id != DISC_ID:
        return await interaction.response.send_message("❌ Dev only.", ephemeral=True)
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = status
    await interaction.response.send_message(f"Maintenance: {'ENABLED 🛠️' if status else 'DISABLED ✅'}")

@bot.tree.command(name="check", description="Check player completions")
async def check(interaction: discord.Interaction, player: str):
    if MAINTENANCE_MODE:
        return await interaction.response.send_message("🛠️ Under maintenance.", ephemeral=True)

    await interaction.response.defer(thinking=True)

    if bot.check_lock.locked():
        return await interaction.followup.send("⏳ Bot busy. Wait 5s.")

    async with bot.check_lock:
        if not csv_loaded:
            return await interaction.followup.send("⚠️ Err 1802: CSV data not loaded.")

        def fetch_data():
            try:
                # Get User ID
                u_req = requests.post("https://users.roblox.com/v1/usernames/users", json={"usernames":[player]}, timeout=10).json()
                if not u_req.get('data'): return "1400", None, None, None
                tid, rname = u_req['data'][0]['id'], u_req['data'][0]['name']

                # Get avatar
                av_res = requests.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={tid}&size=150x150&format=Png&isCircular=false").json()
                avatar_url = av_res['data'][0]['imageUrl'] if 'data' in av_res else None

                # Get badges
                all_ids = []
                try:
                    ts_res = requests.post("https://api.towerstats.com/api/game_badges", json={"id": tid, "universe_id": 9603417152}, headers={"apiKey": TOWERSTATS_KEY}, timeout=10).json()
                    all_ids = ts_res.get('badges', [])
                except:
                    pass

                if not all_ids:
                    cursor = ""
                    while True:
                        res = requests.get(f"https://badges.roblox.com/v1/users/{tid}/badges?limit=100&cursor={cursor}").json()
                        all_ids.extend([b['id'] for b in res.get('data', [])])
                        cursor = res.get('nextPageCursor')
                        if not cursor: break
                return None, rname, all_ids, avatar_url
            except:
                return "1500", None, None, None

        err, rname, badge_ids, avatar_url = await asyncio.get_event_loop().run_in_executor(None, fetch_data)
        if err: return await interaction.followup.send(f"⚠️ Err {err}")

        matched, total_xp, max_d, hardest = [], 0, -1.0, "None"
        for bid in set(map(int, badge_ids)):
            if bid in tower_data and tower_data[bid]['is_tracked']:
                d = tower_data[bid]['difficulty']
                matched.append(f"{EMOJIS.get(int(d), '❓')} **{tower_data[bid]['name']}** [{d}]")
                total_xp += calculate_xp(d)
                if d > max_d: max_d, hardest = d, tower_data[bid]['name']

        save_to_leaderboard(rname, total_xp)

        # Generate Card
        card = Image.new('RGB', (600, 200), color=(35, 39, 42))
        draw = ImageDraw.Draw(card)

        try:
            av_data = requests.get(avatar_url, timeout=5).content
            av_img = Image.open(io.BytesIO(av_data)).resize((150, 150))
            card.paste(av_img, (25, 25))
        except:
            draw.rectangle([25, 25, 175, 175], fill=(50, 50, 50))

        # Note: These use the default tiny font.
        # For better looks, use ImageFont.truetype("arial.ttf", 20)
        draw.text((200, 30), f"TSCR PROFILE: {rname}", fill=(255, 255, 255))
        draw.text((200, 70), f"Total XP: {total_xp:,}", fill=(88, 101, 242))
        draw.text((200, 100), f"Towers: {len(matched)}", fill=(255, 255, 255))
        draw.text((200, 130), f"Hardest: {hardest}", fill=(240, 71, 71))

        with io.BytesIO() as img_bin:
            card.save(img_bin, 'PNG')
            img_bin.seek(0)
            file = discord.File(fp=img_bin, filename='card.png')

            emb = discord.Embed(title=f"TSCR Stats", color=0x2f3136)
            emb.set_image(url="attachment://card.png")

            list_text = "\n".join(matched) if matched else "No towers found."
            if len(list_text) > 1024:
                emb.add_field(name="Tower List", value="List too long for embed, see card summary.", inline=False)
            else:
                emb.add_field(name="Completed Towers", value=list_text, inline=False)

            await interaction.followup.send(file=file, embed=emb)

# bot.run handles the event loop correctly for discord.py
bot.run(DISC_TOKEN)
