import os
import csv
import json
import discord
import requests
import logging
import asyncio
import io
from PIL import Image, ImageDraw, ImageFont, ImageColor
from discord import app_commands
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger('TowerBot')

# config
DISC_TOKEN = 'Token'
TOWERSTATS_KEY = 'ITS BLUE'
MY_USER_ID = 1282662864586543157  # use your own ID
DB_FILE = "leaderboard.json"
MAINTENANCE_MODE = False # if this is true then no one can use commands othen than you aka MY_USER_ID
FONT_PATH = "Inter.ttf"

EMOJIS = {
    8: "<:Insane:1463889989333942416>",
    9: "<:Extreme:1463890005163511842>",
    10: "<:Terrifying:1463890036318671003>",
    11: "<:Catastrophic:1463890064978477176>",
    12: "<:Horrific:1463890091297472545>",
    13: "<:Unreal:1463890107244482721>"
}

def load_leaderboard():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_to_leaderboard(username, xp):
    data = load_leaderboard()
    data[username] = xp
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

def calculate_xp(diff):
    if diff < 8.0 or diff >= 14.0: return 0
    base = {8: 1500, 9: 2500, 10: 4000, 11: 8000, 12: 15000, 13: 25000}.get(int(diff), 0)
    return base + int((diff - int(diff)) * 250)

tower_data = {}
csv_loaded = False

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CSV_PATH = os.path.join(BASE_DIR, "towers.csv")
    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                bid = int(float(row['badge_id']))
                diff_raw = str(row['difficulty']).replace('*', '').replace('!', '').strip()
                if diff_raw.upper() == "PENDING": continue
                difficulty = float(diff_raw)
                tower_data[bid] = {
                    "name": row['name'],
                    "difficulty": difficulty,
                    "is_tracked": str(row['is_tracked']).strip().lower() == "true"
                }
            except: continue
    csv_loaded = True
except: pass

class TowerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.check_lock = asyncio.Lock()
    async def setup_hook(self):
        await self.tree.sync()

bot = TowerBot()

@bot.tree.command(name="maintenance")
async def maintenance(interaction: discord.Interaction, status: bool):
    if interaction.user.id != MY_USER_ID:
        return await interaction.response.send_message("❌ Restricted.", ephemeral=True)
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = status
    await interaction.response.send_message(f"Maintenance: **{'ENABLED' if status else 'DISABLED'}**.")

@bot.tree.command(name="check")
async def check(interaction: discord.Interaction, player: str):
    if MAINTENANCE_MODE and interaction.user.id != MY_USER_ID:
        return await interaction.response.send_message("🛠️ Maintenance.", ephemeral=True)

    await interaction.response.defer(thinking=True)
    if bot.check_lock.locked():
        return await interaction.followup.send("⏳ Processing, wait.")

    async with bot.check_lock:
        if not csv_loaded:
            return await interaction.followup.send("⚠️ CSV Error.")

        def fetch_data():
            try:
                u_req = requests.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [player]}, timeout=10).json()
                if not u_req.get('data'): return "1400", None, None, None
                tid, rname = u_req['data'][0]['id'], u_req['data'][0]['name']
                av_res = requests.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={tid}&size=150x150&format=Png&isCircular=false").json()
                avatar_url = av_res['data'][0]['imageUrl'] if 'data' in av_res else None
                all_ids = []
                try:
                    ts_res = requests.post("https://api.towerstats.com/api/game_badges", json={"id": tid, "universe_id": 9603417152}, headers={"apiKey": TOWERSTATS_KEY}, timeout=10).json()
                    all_ids = ts_res.get('badges', [])
                except: pass
                if not all_ids:
                    cursor = ""
                    while True:
                        res = requests.get(f"https://badges.roblox.com/v1/users/{tid}/badges?limit=100&cursor={cursor}").json()
                        all_ids.extend([b['id'] for b in res.get('data', [])])
                        cursor = res.get('nextPageCursor')
                        if not cursor: break
                return None, rname, all_ids, avatar_url
            except: return "1500", None, None, None

        err, rname, badge_ids, avatar_url = await asyncio.get_event_loop().run_in_executor(None, fetch_data)
        if err: return await interaction.followup.send(f"⚠️ API Error {err}")

        matched = []
        total_xp, max_d, hardest = 0, -1.0, "None"
        for bid in set(map(int, badge_ids)):
            if bid in tower_data and tower_data[bid]['is_tracked']:
                d = tower_data[bid]['difficulty']
                matched.append(bid)
                total_xp += calculate_xp(d)
                if d > max_d: max_d, hardest = d, tower_data[bid]['name']

        save_to_leaderboard(rname, total_xp)

        card_width, card_height = 600, 320
        card = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle([0, 0, card_width, card_height], radius=20, fill=(35, 39, 42, 255))

        font_large = ImageFont.truetype(FONT_PATH, 24)
        font_medium = ImageFont.truetype(FONT_PATH, 18)
        font_small = ImageFont.truetype(FONT_PATH, 14)

        draw.text((card_width - 140, 20), "Inspired by jtoh.pro", font=font_small, fill=(100, 100, 100))

        try:
            av_data = requests.get(avatar_url, timeout=5).content
            av_img = Image.open(io.BytesIO(av_data)).convert("RGBA").resize((100, 100))
            mask = Image.new('L', av_img.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 100, 100), fill=255)
            card.paste(av_img, (25, 25), mask)
        except: draw.ellipse([25, 25, 125, 125], fill=(50, 50, 50))

        draw.text((150, 30), f"{rname}", font=font_large, fill=(255, 255, 255))
        leaderboard_data = load_leaderboard()
        lb_pos = (sorted(leaderboard_data.items(), key=lambda x: x[1], reverse=True).index((rname, total_xp)) + 1 if rname in leaderboard_data else "N/A")
        draw.text((150, 65), f"Leaderboard position: {lb_pos}", font=font_small, fill=(88, 101, 242))

        draw.text((150, 100), f"Total XP: {total_xp:,}", font=font_medium, fill=(88, 101, 242))
        draw.text((150, 130), f"Towers Completed: {len(matched)}", font=font_medium, fill=(255, 255, 255))
        draw.text((150, 160), f"Hardest Tower: {hardest}", font=font_medium, fill=(240, 71, 71))

        diff_colors = {8:"#0000FF", 9:"#028AFF", 10:"#00FFFF", 11:"#FFFFFF", 12:"#9691FF", 13:"#4B00C8"}
        def darken(hex_c, factor=0.3):
            hex_c = hex_c.lstrip('#')
            r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
            return (int(r*factor), int(g*factor), int(b*factor))

        bar_x, bar_y, total_bw, bar_h = 25, 210, 550, 25
        diff_groups = {d: [] for d in range(8, 14)}
        for bid, tower in tower_data.items():
            d_int = int(tower['difficulty'])
            if d_int in diff_groups: diff_groups[d_int].append(bid)

        active_diffs = sorted([d for d in diff_groups if len(diff_groups[d]) > 0])
        if active_diffs:
            seg_w = total_bw / len(active_diffs)
            for i, d in enumerate(active_diffs):
                cur_x = bar_x + (i * seg_w)
                comp_in_diff = [b for b in diff_groups[d] if b in set(matched)]
                b_col = diff_colors.get(d, "#888888")
                f_col = ImageColor.getrgb(b_col) if comp_in_diff else darken(b_col)
                draw.rounded_rectangle([cur_x, bar_y, cur_x + seg_w - 4, bar_y + bar_h], radius=6, fill=f_col)
                draw.text((cur_x + 2, bar_y - 18), f"{len(comp_in_diff)}/{len(diff_groups[d])}", font=font_small, fill=(200, 200, 200))

        p_bar_y = 270
        draw.rounded_rectangle([bar_x, p_bar_y, bar_x + total_bw, p_bar_y + bar_h], radius=6, fill=(20, 20, 20))

        if tower_data:
            ratio = len(matched) / len(tower_data)

            if ratio < 0.4:
                p_color = (255, 50, 50)
            elif ratio < 0.8:
                p_color = (255, 215, 0)
            else:
                p_color = (0, 255, 0)

            if ratio > 0:
                draw.rounded_rectangle([bar_x, p_bar_y, bar_x + (total_bw * ratio), p_bar_y + bar_h], radius=6, fill=p_color)

            draw.text((bar_x, p_bar_y - 18), f"{len(matched)}/{len(tower_data)}", font=font_small, fill=p_color)

        with io.BytesIO() as img_bin:
            card.save(img_bin, 'PNG')
            img_bin.seek(0)
            file = discord.File(fp=img_bin, filename='card.png')
            emb = discord.Embed(title="TSCR Stats Summary", color=0x2f3136)
            emb.set_image(url="attachment://card.png")
            await interaction.followup.send(file=file, embed=emb)

@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):
    data = load_leaderboard()
    if not data: return await interaction.response.send_message("Empty.")
    sorted_lb = sorted(data.items(), key=lambda x: x[1], reverse=True)
    text = "\n".join([f"`{i+1}.` **{u}** — {x:,} XP" for i,(u,x) in enumerate(sorted_lb[:10])])
    await interaction.response.send_message(embed=discord.Embed(title="🏆 Leaderboard", description=text, color=0xffd700))

async def main():
    async with bot: await bot.start(DISC_TOKEN)

if __name__=="__main__":
    asyncio.run(main())
