"""
🤖 DENIA AI BOT - FINAL PRO v2
Logic: An key hoan toan, chi gui link rut gon. User bat buoc vuot link moi nhan duoc key.
"""
import os, sys, random, string, logging, asyncio, json, re, html
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import httpx
import aiosqlite
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.xah.io/v1/chat/completions").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
YEUMONEY_API_KEY = os.getenv("YEUMONEY_API_KEY", "").strip()
YEUMONEY_API_URL = os.getenv("YEUMONEY_API_URL", "https://yeumoney.com/QL_api.php").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "+84 8 8601 2368").strip()
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0") or 0)

REQ_PER_LINK = int(os.getenv("REQ_PER_LINK", "300"))
MAX_REQ_BALANCE = int(os.getenv("MAX_REQ_BALANCE", "5000"))
KEY_COOLDOWN_MINUTES = int(os.getenv("KEY_COOLDOWN_MINUTES", "15"))
KEY_EXPIRE_MINUTES = int(os.getenv("KEY_EXPIRE_MINUTES", "120"))
MAX_KEYS_PER_DAY = int(os.getenv("MAX_KEYS_PER_DAY", "10"))
CHAT_COOLDOWN_SECONDS = int(os.getenv("CHAT_COOLDOWN_SECONDS", "3"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek-v4-flash").strip()
MAX_MEMORY_MESSAGES = int(os.getenv("MAX_MEMORY_MESSAGES", "20"))
SYSTEM_PROMPT_DEFAULT = os.getenv("SYSTEM_PROMPT_DEFAULT", "Ban la Denia AI...").strip()
DAILY_CHECKIN_REQ = int(os.getenv("DAILY_CHECKIN_REQ", "20"))
REFERRAL_BONUS_REQ = int(os.getenv("REFERRAL_BONUS_REQ", "50"))
MAINTENANCE_MODE = int(os.getenv("MAINTENANCE_MODE", "0"))
AUTO_CLEANUP_DAYS = int(os.getenv("AUTO_CLEANUP_DAYS", "7"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("DeniaBot")

DB_PATH = os.path.join(os.path.dirname(__file__), "denia_pro.db")
ADMIN_ID = ADMIN_TELEGRAM_ID

MODEL_PRICES = {}
for k, v in os.environ.items():
    if k.startswith("PRICE_"):
        model_key = k[6:].replace("_", "-").replace("--", "/")
        MODEL_PRICES[model_key] = int(v)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                req_balance INTEGER DEFAULT 0, total_keys_used INTEGER DEFAULT 0, total_messages INTEGER DEFAULT 0,
                last_key_at TIMESTAMP, keys_today INTEGER DEFAULT 0, last_key_date TEXT,
                selected_model TEXT, selected_prompt TEXT DEFAULT 'default', banned INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE, referred_by INTEGER, daily_checkin_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                key_code TEXT PRIMARY KEY, user_id INTEGER, used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (user_id INTEGER PRIMARY KEY, last_chat_at TIMESTAMP)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS model_prices (
                model_name TEXT PRIMARY KEY, req_price INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (name TEXT PRIMARY KEY, content TEXT, enabled INTEGER DEFAULT 1)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS runtime_config (
                key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT,
                status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER UNIQUE,
                bonus_given INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        defaults = [
            ("REQ_PER_LINK", str(REQ_PER_LINK)), ("MAX_REQ_BALANCE", str(MAX_REQ_BALANCE)),
            ("KEY_COOLDOWN_MINUTES", str(KEY_COOLDOWN_MINUTES)), ("KEY_EXPIRE_MINUTES", str(KEY_EXPIRE_MINUTES)),
            ("MAX_KEYS_PER_DAY", str(MAX_KEYS_PER_DAY)), ("CHAT_COOLDOWN_SECONDS", str(CHAT_COOLDOWN_SECONDS)),
            ("DEFAULT_MODEL", DEFAULT_MODEL), ("MAX_MEMORY_MESSAGES", str(MAX_MEMORY_MESSAGES)),
            ("SYSTEM_PROMPT_DEFAULT", SYSTEM_PROMPT_DEFAULT), ("DAILY_CHECKIN_REQ", str(DAILY_CHECKIN_REQ)),
            ("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)), ("MAINTENANCE_MODE", str(MAINTENANCE_MODE)),
            ("AUTO_CLEANUP_DAYS", str(AUTO_CLEANUP_DAYS)),
        ]
        for k, v in defaults:
            await db.execute("INSERT OR IGNORE INTO runtime_config (key, value) VALUES (?, ?)", (k, v))
        await db.execute("INSERT OR IGNORE INTO prompts (name, content) VALUES (?, ?)", ("default", SYSTEM_PROMPT_DEFAULT))
        await db.execute("INSERT OR IGNORE INTO prompts (name, content) VALUES (?, ?)", ("creative", "Ban la Denia AI Creative - Nha van, nghe si sang tao. Tra loi bay bong, giau cam xuc, dung an du, tu ngu my le."))
        await db.execute("INSERT OR IGNORE INTO prompts (name, content) VALUES (?, ?)", ("coder", "Ban la Denia AI Coder - Lap trinh vien cao cap. Tra loi bang code, giai thich ky thuat chinh xac, dung markdown, neu vi du ro rang."))
        await db.execute("INSERT OR IGNORE INTO prompts (name, content) VALUES (?, ?)", ("teacher", "Ban la Denia AI Teacher - Giao vien kien nhan. Giai thich tu co ban den nang cao, dung vi du thuc te, khuyen khich nguoi hoc."))
        await db.commit()

async def get_runtime_config(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM runtime_config WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default

async def set_runtime_config(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO runtime_config (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()))
        await db.commit()

async def get_all_runtime_config() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT key, value FROM runtime_config")
        return {k: v for k, v in await cur.fetchall()}

async def get_or_create_user(user_id: int, username: str = None, first_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            ref_code = "REF" + str(user_id) + str(random.randint(1000,9999))
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, selected_model, referral_code)
                VALUES (?, ?, ?, ?, ?)""", (user_id, username, first_name, DEFAULT_MODEL, ref_code))
            await db.commit()
            return {"user_id": user_id, "username": username, "first_name": first_name,
                    "req_balance": 0, "total_keys_used": 0, "total_messages": 0,
                    "last_key_at": None, "keys_today": 0, "last_key_date": None,
                    "selected_model": DEFAULT_MODEL, "selected_prompt": "default",
                    "banned": 0, "referral_code": ref_code, "referred_by": None,
                    "daily_checkin_date": None, "created_at": datetime.now().isoformat()}
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

async def can_create_key(user_id: int) -> tuple:
    cfg = await get_all_runtime_config()
    cooldown = int(cfg.get("KEY_COOLDOWN_MINUTES", KEY_COOLDOWN_MINUTES))
    max_day = int(cfg.get("MAX_KEYS_PER_DAY", MAX_KEYS_PER_DAY))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_key_at, keys_today, last_key_date, banned FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row: return (True, "")
        if row[3]: return (False, "🚫 Tai khoan cua ban da bi khoa. Lien he admin.")
        last_key_at, keys_today, last_key_date = row[0], row[1] or 0, row[2]
        today_str = datetime.now().strftime("%Y-%m-%d")
        if last_key_date != today_str:
            await db.execute("UPDATE users SET keys_today = 0, last_key_date = ? WHERE user_id = ?", (today_str, user_id))
            await db.commit(); keys_today = 0
        if keys_today >= max_day:
            return (False, "Ban da nhan du " + str(max_day) + " key hom nay. Quay lai ngay mai!")
        if last_key_at:
            last = datetime.fromisoformat(last_key_at)
            if datetime.now() - last < timedelta(minutes=cooldown):
                remain = int((timedelta(minutes=cooldown) - (datetime.now() - last)).total_seconds() // 60)
                return (False, "Vui long doi " + str(remain) + " phut nua de nhan key tiep.")
        return (True, "")

async def create_key(user_id: int, key_code: str) -> bool:
    cfg = await get_all_runtime_config()
    expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))
    async with aiosqlite.connect(DB_PATH) as db:
        expires = datetime.now() + timedelta(minutes=expire)
        try:
            await db.execute("INSERT INTO keys (key_code, user_id, expires_at) VALUES (?, ?, ?)", (key_code, user_id, expires.isoformat()))
            today_str = datetime.now().strftime("%Y-%m-%d")
            await db.execute("""
                UPDATE users SET last_key_at = ?, keys_today = keys_today + 1, last_key_date = ?
                WHERE user_id = ?""", (datetime.now().isoformat(), today_str, user_id))
            await db.commit(); return True
        except Exception as e:
            logger.error("create_key error: " + str(e)); return False

async def use_key(key_code: str, user_id: int) -> dict:
    cfg = await get_all_runtime_config()
    req_per = int(cfg.get("REQ_PER_LINK", REQ_PER_LINK))
    max_bal = int(cfg.get("MAX_REQ_BALANCE", MAX_REQ_BALANCE))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, used, expires_at FROM keys WHERE key_code = ?", (key_code,))
        row = await cur.fetchone()
        if not row: return {"ok": False, "msg": "❌ Key khong ton tai."}
        key_owner, used, expires_at = row[0], row[1], row[2]
        if used: return {"ok": False, "msg": "❌ Key da duoc su dung."}
        if key_owner != user_id: return {"ok": False, "msg": "❌ Key nay khong thuoc ve ban."}
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
            await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
            await db.commit(); return {"ok": False, "msg": "⏳ Key da het han."}
        cur2 = await db.execute("SELECT req_balance FROM users WHERE user_id = ?", (user_id,))
        bal = (await cur2.fetchone())[0] or 0
        if bal + req_per > max_bal: return {"ok": False, "msg": "💎 Ban da dat gioi han " + str(max_bal) + " req."}
        await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
        await db.execute("UPDATE users SET req_balance = req_balance + ?, total_keys_used = total_keys_used + 1 WHERE user_id = ?", (req_per, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "USE_KEY", key_code + " +" + str(req_per) + "req"))
        await db.commit()
        return {"ok": True, "msg": "✅ Key hop le! +" + str(req_per) + " req."}

async def deduct_req(user_id: int, amount: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT req_balance, banned FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row or row[1] or (row[0] or 0) < amount: return False
        await db.execute("UPDATE users SET req_balance = req_balance - ?, total_messages = total_messages + 1 WHERE user_id = ?", (amount, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "CHAT", "-" + str(amount) + "req"))
        await db.commit(); return True

async def check_chat_cooldown(user_id: int) -> tuple:
    cfg = await get_all_runtime_config()
    cd = int(cfg.get("CHAT_COOLDOWN_SECONDS", CHAT_COOLDOWN_SECONDS))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_chat_at FROM cooldowns WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row and row[0]:
            last = datetime.fromisoformat(row[0])
            diff = (datetime.now() - last).total_seconds()
            if diff < cd: return (False, int(cd - diff))
        await db.execute("INSERT OR REPLACE INTO cooldowns (user_id, last_chat_at) VALUES (?, ?)", (user_id, datetime.now().isoformat()))
        await db.commit(); return (True, 0)

async def set_user_model(user_id: int, model: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model, user_id)); await db.commit()
async def get_user_model(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT selected_model FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone(); return row[0] if row and row[0] else DEFAULT_MODEL
async def set_user_prompt(user_id: int, prompt_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET selected_prompt = ? WHERE user_id = ?", (prompt_name, user_id)); await db.commit()
async def get_user_prompt(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT selected_prompt FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone(); return row[0] if row and row[0] else "default"
async def get_prompt_content(name: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT content FROM prompts WHERE name = ? AND enabled = 1", (name,))
        row = await cur.fetchone(); return row[0] if row else SYSTEM_PROMPT_DEFAULT
async def get_all_prompts() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, content, enabled FROM prompts"); return await cur.fetchall()
async def add_conversation(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        cfg = await get_all_runtime_config(); max_mem = int(cfg.get("MAX_MEMORY_MESSAGES", MAX_MEMORY_MESSAGES))
        cur = await db.execute("SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, 1000, max_mem))
        rows = await cur.fetchall()
        if rows:
            ids = [str(r[0]) for r in rows]
            await db.execute("DELETE FROM conversations WHERE id IN (" + ",".join(ids) + ")")
        await db.commit()
async def get_conversation_history(user_id: int, limit: int = None) -> list:
    if limit is None:
        cfg = await get_all_runtime_config(); limit = int(cfg.get("MAX_MEMORY_MESSAGES", MAX_MEMORY_MESSAGES))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT role, content FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        rows = await cur.fetchall(); return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
async def clear_conversation(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,)); await db.commit()
async def get_model_prices() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT model_name, req_price, enabled FROM model_prices")
        rows = await cur.fetchall(); return {r[0]: {"price": r[1], "enabled": r[2]} for r in rows}
async def set_model_price(model_name: str, price: int, enabled: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO model_prices (model_name, req_price, enabled) VALUES (?, ?, ?)", (model_name, price, enabled)); await db.commit()
async def init_model_prices():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM model_prices"); count = (await cur.fetchone())[0]
        if count == 0:
            for k, v in os.environ.items():
                if k.startswith("PRICE_"):
                    model_name = k[6:].replace("_", "-").replace("--", "/")
                    await db.execute("INSERT INTO model_prices (model_name, req_price, enabled) VALUES (?, ?, ?)", (model_name, int(v), 1))
            await db.commit()
async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users"); total_users = (await cur.fetchone())[0]
        cur = await db.execute("SELECT SUM(req_balance) FROM users"); total_req = (await cur.fetchone())[0] or 0
        cur = await db.execute("SELECT COUNT(*) FROM keys WHERE used = 1"); total_keys = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM keys WHERE used = 0"); pending_keys = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM conversations"); total_messages = (await cur.fetchone())[0]
        today = datetime.now().strftime("%Y-%m-%d")
        cur = await db.execute("SELECT COUNT(*) FROM logs WHERE DATE(created_at) = ?", (today,)); today_logs = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM feedback WHERE status = 'pending'")
        pending_feedback = (await cur.fetchone())[0]
        return {"total_users": total_users, "total_req": total_req, "total_keys": total_keys,
                "pending_keys": pending_keys, "total_messages": total_messages, "today_logs": today_logs,
                "pending_feedback": pending_feedback}
async def get_users_list(limit: int = 50, offset: int = 0) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, username, first_name, req_balance, total_keys_used, total_messages, banned, created_at, selected_model, selected_prompt
            FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?""", (limit, offset)); return await cur.fetchall()
async def get_top_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, first_name, username, total_messages, req_balance FROM users ORDER BY total_messages DESC LIMIT 10")
        return await cur.fetchall()
async def admin_add_req(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET req_balance = req_balance + ? WHERE user_id = ?", (amount, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "ADMIN_ADD", "+" + str(amount) + "req")); await db.commit()
async def admin_ban_user(user_id: int, ban: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned = ? WHERE user_id = ?", (ban, user_id)); await db.commit()
async def get_user_logs(user_id: int, limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT action, detail, created_at FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)); return await cur.fetchall()
async def get_recent_logs(limit: int = 50) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT l.user_id, u.username, l.action, l.detail, l.created_at
            FROM logs l LEFT JOIN users u ON l.user_id = u.user_id ORDER BY l.id DESC LIMIT ?""", (limit,)); return await cur.fetchall()
async def get_all_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users"); return [r[0] for r in await cur.fetchall()]
async def add_feedback(user_id: int, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO feedback (user_id, content) VALUES (?, ?)", (user_id, content)); await db.commit()
async def get_pending_feedback(limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT f.id, f.user_id, u.username, f.content, f.created_at
            FROM feedback f LEFT JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'pending' ORDER BY f.id DESC LIMIT ?""", (limit,)); return await cur.fetchall()
async def mark_feedback_done(feedback_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE feedback SET status = 'done' WHERE id = ?", (feedback_id,)); await db.commit()
async def check_referral(referrer_id: int, referred_id: int) -> bool:
    if referrer_id == referred_id: return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,))
        if await cur.fetchone(): return False
        await db.execute("INSERT INTO referrals (referrer_id, referred_id, bonus_given) VALUES (?, ?, 1)", (referrer_id, referred_id))
        bonus = int(await get_runtime_config("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
        await db.execute("UPDATE users SET req_balance = req_balance + ? WHERE user_id = ?", (bonus, referrer_id))
        await db.execute("UPDATE users SET req_balance = req_balance + ? WHERE user_id = ?", (bonus, referred_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (referred_id, "REFERRAL", "Invited by " + str(referrer_id) + ", +" + str(bonus) + "req")); await db.commit(); return True
async def daily_checkin(user_id: int) -> tuple:
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT daily_checkin_date, req_balance FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row: return (False, 0)
        if row[0] == today: return (False, 0)
        bonus = int(await get_runtime_config("DAILY_CHECKIN_REQ", str(DAILY_CHECKIN_REQ)))
        await db.execute("UPDATE users SET daily_checkin_date = ?, req_balance = req_balance + ? WHERE user_id = ?", (today, bonus, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "CHECKIN", "+" + str(bonus) + "req")); await db.commit(); return (True, bonus)
async def auto_cleanup():
    days = int(await get_runtime_config("AUTO_CLEANUP_DAYS", str(AUTO_CLEANUP_DAYS)))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM logs WHERE created_at < ?", (cutoff,))
        await db.execute("DELETE FROM keys WHERE used = 0 AND created_at < ?", (cutoff,))
        await db.execute("DELETE FROM conversations WHERE created_at < ?", (cutoff,)); await db.commit()
        logger.info("Auto cleanup completed (older than " + str(days) + " days)")

def generate_key() -> str:
    p1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    p2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=2))
    p3 = "".join(random.choices(string.ascii_uppercase + string.digits, k=13))
    p4 = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return "denia-" + p1 + "-" + p2 + "-" + p3 + "-" + p4

async def shorten_yeumoney(long_url: str) -> str | None:
    if not YEUMONEY_API_KEY or not YEUMONEY_API_URL: return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            import urllib.parse
            encoded_url = urllib.parse.quote(long_url, safe='')
            api_call = YEUMONEY_API_URL + "?token=" + YEUMONEY_API_KEY + "&url=" + encoded_url + "&format=json"
            r = await client.get(api_call)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success" and "shortenedUrl" in data: return data["shortenedUrl"]
                logger.warning("Yeumoney response: " + str(data))
    except Exception as e: logger.warning("Yeumoney API error: " + str(e))
    return None

async def chat_ai(user_id: int, user_message: str) -> tuple[str, int]:
    model = await get_user_model(user_id)
    prices = await get_model_prices(); req_cost = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            if v["enabled"]: req_cost = v["price"]; break
    prompt_name = await get_user_prompt(user_id)
    system_prompt = await get_prompt_content(prompt_name)
    history = await get_conversation_history(user_id)
    messages = [{"role": "system", "content": system_prompt}]; messages.extend(history); messages.append({"role": "user", "content": user_message})
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(AI_BASE_URL, headers={"Authorization": "Bearer " + AI_API_KEY, "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.7})
            data = r.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"]
                await add_conversation(user_id, "user", user_message); await add_conversation(user_id, "assistant", reply); return (reply, req_cost)
            return ("❌ AI khong tra loi. Thu lai sau.", 0)
    except Exception as e: logger.error("AI error: " + str(e)); return ("❌ AI dang ban. Vui long thu lai sau.", 0)

def get_model_price(model: str) -> int:
    model_key = model.replace("/", "-").lower()
    for k, v in MODEL_PRICES.items():
        if k.lower() in model_key or model_key in k.lower(): return v
    return 1

ADMIN_ID = ADMIN_TELEGRAM_ID
def is_admin(user_id: int) -> bool:
    global ADMIN_ID
    if ADMIN_ID == 0: return False
    return user_id == ADMIN_ID
async def auto_set_admin(user_id: int):
    global ADMIN_ID
    if ADMIN_ID == 0: ADMIN_ID = user_id; logger.info("Auto-set admin: " + str(user_id))
async def is_maintenance() -> bool:
    cfg = await get_all_runtime_config(); return cfg.get("MAINTENANCE_MODE", str(MAINTENANCE_MODE)) == "1"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # Xu ly Deep Link auto verify key (sau khi vuot Yeumoney)
    if args and len(args) > 0:
        key_input = args[0].strip().upper()
        if key_input.startswith("DENIA-"):
            u = await get_or_create_user(user.id, user.username, user.first_name)
            if u["banned"]:
                await update.message.reply_text("🚫 Tài khoản của bạn đã bị khóa. Liên hệ admin.")
                return
            result = await use_key(key_input, user.id)
            if result["ok"]:
                await update.message.reply_text(
                    "🎉 <b>Chào mừng trở lại!</b>\n\n"
                    + result["msg"] + "\n\n"
                    "✨ Bạn có thể bắt đầu chat AI ngay bây giờ!\n"
                    "💡 Gõ /help để xem hướng dẫn chi tiết.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text("⚠️ " + result["msg"], parse_mode=ParseMode.HTML)
            return
        # Xu ly referral
        elif args[0].startswith("REF"):
            referrer_code = args[0].strip()
            u = await get_or_create_user(user.id, user.username, user.first_name)
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
                row = await cur.fetchone()
                if row and row[0] != user.id and not u.get("referred_by"):
                    success = await check_referral(row[0], user.id)
                    if success:
                        bonus = int(await get_runtime_config("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
                        await update.message.reply_text(
                            "🎉 <b>Chào mừng!</b> Bạn được mời bởi user <code>" + str(row[0]) + "</code>.\n"
                            "💎 Cả 2 bạn đều nhận +" + str(bonus) + " req!",
                            parse_mode=ParseMode.HTML
                        )
                        try:
                            await context.bot.send_message(row[0],
                                "🎉 <b>Chúc mừng!</b> User <code>" + str(user.id) + "</code> đã dùng mã giới thiệu của bạn.\n"
                                "💎 Bạn nhận +" + str(bonus) + " req!", parse_mode=ParseMode.HTML)
                        except Exception: pass
                        return

    u = await get_or_create_user(user.id, user.username, user.first_name)
    if u["banned"]:
        await update.message.reply_text("🚫 Tài khoản của bạn đã bị khóa. Liên hệ admin.")
        return

    prices = await get_model_prices()
    price_list = "\n".join(["• <code>" + html.escape(k) + "</code>: " + str(v['price']) + " req" for k, v in prices.items() if v['enabled']])

    keyboard = [
        [InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")],
        [InlineKeyboardButton("📅 Điểm Danh", callback_data="checkin"), InlineKeyboardButton("💎 Số Dư", callback_data="balance")],
        [InlineKeyboardButton("🤖 Chọn Model", callback_data="models"), InlineKeyboardButton("🎭 Tính Cách", callback_data="prompts")],
        [InlineKeyboardButton("🏆 Bảng Xếp Hạng", callback_data="top"), InlineKeyboardButton("📞 Hỗ Trợ", callback_data="support")]
    ]

    await update.message.reply_text(
        "👋 <b>Xin chào " + html.escape(user.first_name or "bạn") + "!</b>\n\n"
        "🤖 <b>Denia AI Bot</b> — Trợ lý AI thông minh, có trí nhớ!\n\n"
        "💎 <b>Số dư:</b> <code>" + str(u['req_balance']) + " req</code>\n"
        "⚙️ <b>Model:</b> <code>" + html.escape(u['selected_model'] or DEFAULT_MODEL) + "</code>\n"
        "🎭 <b>Tính cách:</b> <code>" + str(u['selected_prompt']) + "</code>\n"
        "💰 <b>Giá chat:</b> <code>" + str(get_model_price(u['selected_model'] or DEFAULT_MODEL)) + " req</code>/tin nhắn\n\n"
        "<b>📋 Bảng giá model:</b>\n" + price_list + "\n\n"
        "🎁 <b>Mã giới thiệu:</b> <code>" + str(u['referral_code']) + "</code>\n"
        "💡 Gõ <code>/help</code> để xem hướng dẫn chi tiết.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>Hướng Dẫn Sử Dụng — Denia AI</b>\n\n"
        "<b>🎯 Cách nhận req (bước đơn giản):</b>\n"
        "1️⃣ Nhấn <b>🔑 Nhận Key Mới</b> trên menu\n"
        "2️⃣ Bot tạo link rút gọn qua Yeumoney\n"
        "3️⃣ <b>Copy link</b> → mở trình duyệt (Chrome/Safari)\n"
        "4️⃣ Vượt Yeumoney (chờ 15-30 giây)\n"
        "5️⃣ Sau khi vượt xong, click <b>'Tiếp tục'</b> → Telegram mở ra\n"
        "6️⃣ Nhấn <b>Start</b> → Bot tự động cộng req!\n\n"
        "<b>🎭 Lệnh nâng cao:</b>\n"
        "• <code>/model</code> — Chọn model AI\n"
        "• <code>/prompt</code> — Chọn tính cách AI\n"
        "• <code>/new</code> — Xóa lịch sử chat\n"
        "• <code>/history</code> — Xem lịch sử\n"
        "• <code>/profile</code> — Hồ sơ cá nhân\n"
        "• <code>/top</code> — Bảng xếp hạng\n"
        "• <code>/checkin</code> — Điểm danh nhận req\n"
        "• <code>/ref</code> — Mã giới thiệu\n"
        "• <code>/feedback</code> — Góp ý cho admin\n\n"
        "<b>⚠️ Lưu ý:</b>\n"
        "• Mỗi tin nhắn AI tốn req tùy model (1-5 req)\n"
        "• Nhận key cách nhau 15 phút, tối đa 10 key/ngày\n"
        "• Giới hạn tích lũy: 5000 req\n"
        "• Key hết hạn sau 120 phút nếu không dùng\n\n"
        "📞 <b>Hỗ trợ:</b> " + ADMIN_PHONE,
        parse_mode=ParseMode.HTML
    )

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "⚠️ Vui lòng gửi kèm mã key.\n"
            "Ví dụ: <code>/key denia-A1B2C3-D4-E5F6G7H8I9J10-K11</code>",
            parse_mode=ParseMode.HTML
        ); return
    key_input = context.args[0].strip().upper()
    if not key_input.startswith("DENIA-"):
        await update.message.reply_text("❌ Key phải bắt đầu bằng <code>denia-</code>", parse_mode=ParseMode.HTML); return
    result = await use_key(key_input, user_id)
    await update.message.reply_text(result["msg"], parse_mode=ParseMode.HTML)

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prices = await get_model_prices()
    if not context.args:
        current = await get_user_model(user_id)
        buttons = []; row = []
        for k, v in prices.items():
            if v["enabled"]:
                row.append(InlineKeyboardButton(k[:18] + " (" + str(v['price']) + "r)", callback_data="setmodel|" + k))
                if len(row) == 2: buttons.append(row); row = []
        if row: buttons.append(row)
        await update.message.reply_text(
            "⚙️ <b>Model hiện tại:</b> <code>" + html.escape(current) + "</code>\n\n"
            "Chọn model bên dưới:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        ); return
    model_name = " ".join(context.args).strip(); found = False
    for k in prices.keys():
        if model_name.lower() in k.lower() or k.lower() in model_name.lower():
            if prices[k]["enabled"]: model_name = k; found = True; break
    if not found: await update.message.reply_text("❌ Model không hợp lệ hoặc đã bị tắt."); return
    await set_user_model(user_id, model_name)
    await update.message.reply_text(
        "✅ Đã chuyển sang model: <code>" + html.escape(model_name) + "</code>\n"
        "💰 Giá: " + str(prices[model_name]['price']) + " req/tin nhắn", parse_mode=ParseMode.HTML
    )

async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompts = await get_all_prompts()
    if not context.args:
        current = await get_user_prompt(user_id)
        buttons = []
        for name, content, enabled in prompts:
            if enabled: buttons.append([InlineKeyboardButton(name.upper(), callback_data="setprompt|" + name)])
        await update.message.reply_text(
            "🎭 <b>Tính cách hiện tại:</b> <code>" + current + "</code>\n\n"
            "Chọn tính cách bên dưới:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        ); return
    name = context.args[0].strip().lower(); valid = [p[0] for p in prompts if p[2]]
    if name not in valid: await update.message.reply_text("❌ Tính cách không hợp lệ. Các lựa chọn: " + ", ".join(valid)); return
    await set_user_prompt(user_id, name)
    await update.message.reply_text(
        "🎭 Đã chuyển sang tính cách: <b>" + name.upper() + "</b>\n"
        "AI sẽ trả lời theo phong cách mới từ tin nhắn tiếp theo.", parse_mode=ParseMode.HTML
    )

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await clear_conversation(user_id)
    await update.message.reply_text(
        "🧠 <b>Đã xóa lịch sử chat!</b>\n\n"
        "AI không còn nhớ gì về cuộc trò chuyện trước.\n"
        "Bạn có thể bắt đầu chủ đề mới ngay bây giờ.", parse_mode=ParseMode.HTML
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hist = await get_conversation_history(user_id, limit=10)
    if not hist: await update.message.reply_text("📝 Chưa có lịch sử chat nào."); return
    text = "📝 <b>Lịch sử chat gần đây:</b>\n\n"
    for msg in hist:
        role = "👤 Bạn" if msg["role"] == "user" else "🤖 AI"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        text += role + ": " + html.escape(content) + "\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_or_create_user(user_id)
    model = u["selected_model"] or DEFAULT_MODEL
    prices = await get_model_prices(); price = 1
    for k,v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower(): price = v["price"]; break
    text = (
        "👤 <b>Hồ sơ của bạn</b>\n\n"
        "🆔 <b>ID:</b> <code>" + str(u['user_id']) + "</code>\n"
        "👤 <b>Tên:</b> " + html.escape(u['first_name'] or 'N/A') + "\n"
        "💎 <b>Số dư:</b> <code>" + str(u['req_balance']) + " req</code>\n"
        "🔑 <b>Đã dùng:</b> " + str(u['total_keys_used']) + " key\n"
        "💬 <b>Tin nhắn:</b> " + str(u['total_messages']) + "\n"
        "📅 <b>Tham gia:</b> " + (u['created_at'][:10] if u['created_at'] else 'N/A') + "\n"
        "⚙️ <b>Model:</b> <code>" + html.escape(model) + "</code>\n"
        "🎭 <b>Tính cách:</b> <code>" + str(u['selected_prompt']) + "</code>\n"
        "💰 <b>Giá chat:</b> " + str(price) + " req/tin nhắn\n"
        "🎁 <b>Mã giới thiệu:</b> <code>" + str(u['referral_code']) + "</code>\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = await get_top_users()
    if not top: await update.message.reply_text("🏆 Chưa có dữ liệu xếp hạng."); return
    text = "🏆 <b>Bảng xếp hạng — Top 10</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, u in enumerate(top):
        name = html.escape(u[1] or u[2] or "User " + str(u[0]))
        text += medals[i] + " <b>" + name + "</b> — " + str(u[3]) + " tin nhắn | " + str(u[4]) + " req\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ok, bonus = await daily_checkin(user_id)
    if ok:
        await update.message.reply_text(
            "📅 <b>Điểm danh thành công!</b>\n\n"
            "💎 Bạn nhận +" + str(bonus) + " req miễn phí!\n"
            "🌟 Hẹn gặp lại bạn vào ngày mai!", parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "⚠️ <b>Bạn đã điểm danh hôm nay rồi!</b>\n\n"
            "🌅 Hãy quay lại vào ngày mai để nhận thêm req nhé.", parse_mode=ParseMode.HTML
        )

async def ref_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_or_create_user(user_id)
    bonus = int(await get_runtime_config("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
    link = "https://t.me/" + context.bot.username + "?start=" + u['referral_code']
    await update.message.reply_text(
        "🎁 <b>Mã giới thiệu của bạn</b>\n\n"
        "🔗 <b>Link mời:</b> <code>" + link + "</code>\n\n"
        "💎 <b>Phần thưởng:</b> Mỗi lượt mời thành công, cả 2 đều nhận +" + str(bonus) + " req!\n"
        "📤 <b>Hướng dẫn:</b> Chia sẻ link bên trên cho bạn bè. Khi họ nhấn Start, cả 2 đều được thưởng.",
        parse_mode=ParseMode.HTML
    )

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "📣 Vui lòng gửi kèm nội dung góp ý.\n"
            "Ví dụ: <code>/feedback Bot rất hay, cảm ơn admin!</code>", parse_mode=ParseMode.HTML
        ); return
    content = " ".join(context.args).strip()
    await add_feedback(user_id, content)
    await update.message.reply_text(
        "✅ <b>Cảm ơn bạn đã góp ý!</b>\n\n"
        "Admin sẽ xem xét và phản hồi sớm nhất.", parse_mode=ParseMode.HTML
    )
    try:
        if ADMIN_ID and ADMIN_ID != 0:
            await context.bot.send_message(ADMIN_ID,
                "📣 <b>Feedback mới từ</b> <code>" + str(user_id) + "</code>:\n" + html.escape(content[:500]),
                parse_mode=ParseMode.HTML)
    except Exception: pass

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "getkey":
        ok, msg = await can_create_key(user_id)
        if not ok:
            await query.edit_message_text("⚠️ " + msg, parse_mode=ParseMode.HTML); return

        key = generate_key()
        await create_key(user_id, key)

        bot_username = context.bot.username
        if not bot_username:
            await query.edit_message_text("❌ Lỗi: Bot chưa có username. Vui lòng liên hệ admin.", parse_mode=ParseMode.HTML); return

        # Tạo Telegram Deep Link chứa key (ẨN - user không thấy key)
        deep_link = "https://t.me/" + bot_username + "?start=" + key

        # Rút gọn qua Yeumoney
        short_link = await shorten_yeumoney(deep_link)

        cfg = await get_all_runtime_config()
        expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))

        if short_link:
            # CÓ link rút gọn → Chỉ gửi link, KHÔNG hiển thị key
            text = (
                "🔐 <b>Link vượt của bạn đã sẵn sàng!</b>\n\n"
                "🔗 <b>Link rút gọn:</b>\n"
                "<code>" + html.escape(short_link) + "</code>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📋 <b>Hướng dẫn vượt link (3 bước):</b>\n\n"
                "1️⃣ <b>Copy link</b> bên trên\n"
                "2️⃣ Mở <b>trình duyệt</b> (Chrome/Safari) → Dán link → Enter\n"
                "3️⃣ Vượt Yeumoney (chờ 15-30 giây) → Click <b>'Tiếp tục'</b> → Telegram mở ra\n\n"
                "✅ Nhấn <b>Start</b> trên Telegram → Bot <b>tự động</b> cộng " + str(REQ_PER_LINK) + " req!\n\n"
                "⏳ <b>Key hết hạn sau:</b> " + str(expire) + " phút\n"
                "💡 <b>Lưu ý:</b> Không thoát khỏi trang Yeumoney trước khi click Tiếp tục"
            )
        else:
            # KHÔNG rút gọn được → Fallback: gửi link gốc (ít an toàn hơn nhưng vẫn hoạt động)
            text = (
                "⚠️ <b>Bot chưa rút gọn được link.</b>\n\n"
                "🔗 <b>Link gốc (bạn cần tự rút gọn qua Yeumoney):</b>\n"
                "<code>" + html.escape(deep_link) + "</code>\n\n"
                "📋 <b>Cách làm:</b>\n"
                "1. Vào yeumoney.com → rút gọn link bên trên\n"
                "2. Copy link rút gọn → mở trình duyệt → vượt\n"
                "3. Sau khi vượt xong, Telegram sẽ mở → Nhấn Start\n\n"
                "⏳ <b>Key hết hạn sau:</b> " + str(expire) + " phút"
            )

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    elif data == "balance":
        u = await get_or_create_user(user_id)
        model = u["selected_model"] or DEFAULT_MODEL
        prices = await get_model_prices(); price = 1
        for k,v in prices.items():
            if k.lower() in model.lower() or model.lower() in k.lower(): price = v["price"]; break
        await query.edit_message_text(
            "💎 <b>Số dư tài khoản</b>\n\n"
            "💰 <b>Req hiện có:</b> <code>" + str(u['req_balance']) + " req</code>\n"
            "🔑 <b>Key đã dùng:</b> " + str(u['total_keys_used']) + "\n"
            "📅 <b>Hôm nay:</b> " + str(u['keys_today']) + "/10 key\n"
            "💬 <b>Tin nhắn:</b> " + str(u['total_messages']) + "\n"
            "⚙️ <b>Model:</b> <code>" + html.escape(model) + "</code>\n"
            "🎭 <b>Tính cách:</b> <code>" + str(u['selected_prompt']) + "</code>\n"
            "💵 <b>Giá chat:</b> " + str(price) + " req/tin nhắn\n\n"
            "🎁 <b>Mã giới thiệu:</b> <code>" + str(u['referral_code']) + "</code>",
            parse_mode=ParseMode.HTML
        )

    elif data == "models":
        prices = await get_model_prices()
        buttons = []; row = []
        for k, v in prices.items():
            if v["enabled"]:
                row.append(InlineKeyboardButton(k[:15] + " (" + str(v['price']) + "r)", callback_data="setmodel|" + k))
                if len(row) == 2: buttons.append(row); row = []
        if row: buttons.append(row)
        await query.edit_message_text(
            "🤖 <b>Chọn Model AI</b>\n\n"
            "💡 <b>Gợi ý:</b>\n"
            "• Model <b>1 req</b> = Nhanh, phù hợp chat thường\n"
            "• Model <b>3-5 req</b> = Thông minh hơn, chuyên sâu\n\n"
            "Chọn model bên dưới:",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        )

    elif data == "prompts":
        prompts = await get_all_prompts()
        buttons = []
        for name, content, enabled in prompts:
            if enabled: buttons.append([InlineKeyboardButton(name.upper(), callback_data="setprompt|" + name)])
        await query.edit_message_text(
            "🎭 <b>Chọn Tính Cách AI</b>\n\n"
            "• <b>DEFAULT</b> — Trợ lý cân bằng, đa năng\n"
            "• <b>CREATIVE</b> — Bay bổng, giàu cảm xúc\n"
            "• <b>CODER</b> — Lập trình viên chuyên nghiệp\n"
            "• <b>TEACHER</b> — Giáo viên kiên nhẫn\n\n"
            "Chọn tính cách bên dưới:",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        )

    elif data == "support":
        await query.edit_message_text(
            "📞 <b>Hỗ Trợ Denia AI</b>\n\n"
            "📱 <b>Zalo / Telegram:</b> <code>" + ADMIN_PHONE + "</code>\n"
            "⏰ <b>Giờ hỗ trợ:</b> 08:00 — 22:00 (GMT+7)\n\n"
            "⚠️ Vui lòng không spam tin nhắn.\n"
            "💬 Mô tả rõ vấn đề để được hỗ trợ nhanh nhất.",
            parse_mode=ParseMode.HTML
        )

    elif data == "top":
        top = await get_top_users()
        if not top: await query.edit_message_text("🏆 Chưa có dữ liệu xếp hạng."); return
        text = "🏆 <b>Bảng Xếp Hạng — Top 10</b>\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, u in enumerate(top):
            name = html.escape(u[1] or u[2] or "User " + str(u[0]))
            text += medals[i] + " <b>" + name + "</b> — " + str(u[3]) + " tin nhắn | " + str(u[4]) + " req\n"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    elif data == "checkin":
        ok, bonus = await daily_checkin(user_id)
        if ok:
            await query.edit_message_text(
                "📅 <b>Điểm danh thành công!</b>\n\n"
                "🎉 Bạn nhận +" + str(bonus) + " req miễn phí!\n"
                "🌟 Hẹn gặp lại bạn vào ngày mai!", parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                "⚠️ <b>Bạn đã điểm danh hôm nay rồi!</b>\n\n"
                "🌅 Hãy quay lại vào ngày mai để nhận thêm req nhé.", parse_mode=ParseMode.HTML
            )

    elif data.startswith("setmodel|"):
        model = data.split("|", 1)[1]
        await set_user_model(user_id, model)
        prices = await get_model_prices(); price = prices.get(model, {}).get("price", 1)
        await query.edit_message_text(
            "✅ <b>Đã chuyển model!</b>\n\n"
            "⚙️ Model: <code>" + html.escape(model) + "</code>\n"
            "💰 Giá: " + str(price) + " req/tin nhắn\n\n"
            "💬 Bắt đầu chat ngay bây giờ!", parse_mode=ParseMode.HTML
        )

    elif data.startswith("setprompt|"):
        name = data.split("|", 1)[1]
        await set_user_prompt(user_id, name)
        await query.edit_message_text(
            "🎭 <b>Đã chuyển tính cách!</b>\n\n"
            "Tính cách: <b>" + name.upper() + "</b>\n"
            "AI sẽ trả lời theo phong cách mới từ tin nhắn tiếp theo.", parse_mode=ParseMode.HTML
        )

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_or_create_user(user_id)
    if u["banned"]: return

    if await is_maintenance() and not is_admin(user_id):
        await update.message.reply_text(
            "🔧 <b>Bot đang bảo trì.</b>\n\n"
            "Vui lòng quay lại sau. Bạn vẫn có thể nhận key và điểm danh.", parse_mode=ParseMode.HTML
        ); return

    ok, remain = await check_chat_cooldown(user_id)
    if not ok:
        await update.message.reply_text("⏳ Vui lòng đợi " + str(remain) + " giây nữa.")
        return

    model = await get_user_model(user_id)
    prices = await get_model_prices(); price = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            if v["enabled"]: price = v["price"]; break
    success = await deduct_req(user_id, price)
    if not success:
        keyboard = [[InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")]]
        await update.message.reply_text(
            "⚠️ <b>Bạn đã hết req!</b>\n\n"
            "Cần " + str(price) + " req để chat model này.\n"
            "Nhấn nút bên dưới để nhận key.",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        ); return

    await update.message.chat.send_action(action="typing")
    try:
        reply, cost = await chat_ai(user_id, update.message.text)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error("Chat handler error: " + str(e))
        await update.message.reply_text("❌ AI đang bận. Vui lòng thử lại sau.")

# ========================
# ADMIN HANDLERS
# ========================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await auto_set_admin(user_id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bạn không có quyền admin.")
        return
    await update.message.reply_text(
        "🔐 <b>ADMIN PANEL — Denia AI</b>\n\n"
        "<b>📊 Thống kê:</b>\n"
        "• <code>/stats</code> — Xem thống kê tổng quan\n"
        "• <code>/logs</code> — Xem 50 hoạt động gần nhất\n"
        "• <code>/health</code> — Kiểm tra hệ thống\n\n"
        "<b>👤 Quản lý Users:</b>\n"
        "• <code>/users</code> — Danh sách users\n"
        "• <code>/user [id]</code> — Chi tiết user\n"
        "• <code>/addreq [id] [số req]</code> — Nạp req\n"
        "• <code>/ban [id]</code> — Khóa user\n"
        "• <code>/unban [id]</code> — Mở khóa user\n\n"
        "<b>⚙️ Cấu hình Bot:</b>\n"
        "• <code>/config</code> — Xem cấu hình hiện tại\n"
        "• <code>/setconfig [key] [value]</code> — Đổi cấu hình\n"
        "• <code>/setprice [model] [giá]</code> — Đổi giá model\n"
        "• <code>/maintenance</code> — Bật/tắt bảo trì\n\n"
        "<b>🤖 Quản lý Model & Prompt:</b>\n"
        "• <code>/models</code> — Quản lý model\n"
        "• <code>/togglemodel [model]</code> — Bật/tắt model\n"
        "• <code>/prompts</code> — Quản lý prompt\n"
        "• <code>/addprompt [tên] [nội dung]</code> — Thêm prompt\n\n"
        "<b>📢 Thông báo & Feedback:</b>\n"
        "• <code>/broadcast [tin nhắn]</code> — Gửi thông báo\n"
        "• <code>/feedbacklist</code> — Xem góp ý chưa đọc\n"
        "• <code>/feedbackdone [id]</code> — Đánh dấu đã xử lý\n\n"
        "<b>🧹 Dọn dẹp:</b>\n"
        "• <code>/cleanup</code> — Xóa dữ liệu cũ\n"
        "• <code>/export</code> — Xuất CSV thống kê\n\n"
        "📞 Admin: " + ADMIN_PHONE,
        parse_mode=ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    stats = await get_stats()
    await update.message.reply_text(
        "📊 <b>Thống Kê Denia AI</b>\n\n"
        "👤 <b>Tổng users:</b> " + str(stats['total_users']) + "\n"
        "💎 <b>Tổng req lưu hành:</b> " + str(stats['total_req']) + "\n"
        "🔑 <b>Key đã dùng:</b> " + str(stats['total_keys']) + "\n"
        "⏳ <b>Key chờ xử lý:</b> " + str(stats['pending_keys']) + "\n"
        "💬 <b>Tin nhắn AI:</b> " + str(stats['total_messages']) + "\n"
        "📅 <b>Hoạt động hôm nay:</b> " + str(stats['today_logs']) + "\n"
        "📣 <b>Feedback chờ:</b> " + str(stats['pending_feedback']) + "\n\n"
        "📞 Admin: " + ADMIN_PHONE,
        parse_mode=ParseMode.HTML
    )

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    logs = await get_recent_logs(50)
    text = "📋 <b>Logs Gần Đây (50):</b>\n\n"
    for l in logs:
        text += "[" + l[4][:16] + "] <code>" + str(l[0]) + "</code> | " + html.escape(l[1] or 'N/A') + " | <b>" + l[2] + "</b> | " + html.escape(l[3]) + "\n"
    if len(text) > 4000: text = text[:4000] + "\n... (còn nhiều)"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    users = await get_users_list(limit=20)
    text = "👤 <b>Danh Sách Users (20 gần nhất):</b>\n\n"
    for u in users:
        status = "🚫 BANNED" if u[6] else "✅ OK"
        name = html.escape(u[2] or u[1] or str(u[0]))
        text += "<code>" + str(u[0]) + "</code> | " + name + " | Req: " + str(u[3]) + " | Keys: " + str(u[4]) + " | Msg: " + str(u[5]) + " | " + status + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def user_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập user ID. Ví dụ: <code>/user 123456789</code>", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0])
    except ValueError: await update.message.reply_text("❌ ID không hợp lệ."); return
    user = await get_or_create_user(target_id); logs = await get_user_logs(target_id, 10)
    text = (
        "👤 <b>Chi Tiết User " + str(target_id) + "</b>\n\n"
        "Username: " + html.escape(user['username'] or 'N/A') + "\n"
        "Tên: " + html.escape(user['first_name'] or 'N/A') + "\n"
        "Req: " + str(user['req_balance']) + "\n"
        "Keys used: " + str(user['total_keys_used']) + "\n"
        "Messages: " + str(user['total_messages']) + "\n"
        "Model: " + html.escape(user['selected_model'] or 'N/A') + "\n"
        "Prompt: " + str(user['selected_prompt']) + "\n"
        "Mã giới thiệu: <code>" + str(user['referral_code']) + "</code>\n"
        "Status: " + ('🚫 BANNED' if user['banned'] else '✅ OK') + "\n"
        "Created: " + str(user['created_at']) + "\n\n"
        "<b>📋 Logs gần đây:</b>\n"
    )
    for l in logs: text += "• " + l[2] + " | " + l[0] + " | " + html.escape(l[1]) + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def addreq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Ví dụ: <code>/addreq 123456789 100</code>", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0]); amount = int(context.args[1])
    except ValueError: await update.message.reply_text("❌ Số không hợp lệ."); return
    await admin_add_req(target_id, amount)
    await update.message.reply_text("✅ Đã nạp " + str(amount) + " req cho user <code>" + str(target_id) + "</code>", parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(target_id,
            "💎 <b>Thông Báo Từ Admin</b>\n\n"
            "Bạn vừa được cộng <b>" + str(amount) + " req</b>!\n"
            "Số dư hiện tại đã được cập nhật.", parse_mode=ParseMode.HTML)
    except Exception: pass

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("⚠️ Ví dụ: <code>/ban 123456789</code>", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0])
    except ValueError: await update.message.reply_text("❌ ID không hợp lệ."); return
    await admin_ban_user(target_id, 1)
    await update.message.reply_text("🚫 Đã khóa user <code>" + str(target_id) + "</code>", parse_mode=ParseMode.HTML)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("⚠️ Ví dụ: <code>/unban 123456789</code>", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0])
    except ValueError: await update.message.reply_text("❌ ID không hợp lệ."); return
    await admin_ban_user(target_id, 0)
    await update.message.reply_text("✅ Đã mở khóa user <code>" + str(target_id) + "</code>", parse_mode=ParseMode.HTML)

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    cfg = await get_all_runtime_config(); text = "⚙️ <b>Cấu Hình Hiện Tại:</b>\n\n"
    for k, v in cfg.items(): text += "• <code>" + html.escape(k) + "</code> = <code>" + html.escape(v) + "</code>\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def setconfig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Ví dụ: <code>/setconfig REQ_PER_LINK 300</code>\n"
            "Các key: REQ_PER_LINK, MAX_REQ_BALANCE, KEY_COOLDOWN_MINUTES, KEY_EXPIRE_MINUTES, MAX_KEYS_PER_DAY, "
            "CHAT_COOLDOWN_SECONDS, MAX_MEMORY_MESSAGES, DAILY_CHECKIN_REQ, REFERRAL_BONUS_REQ, MAINTENANCE_MODE, AUTO_CLEANUP_DAYS",
            parse_mode=ParseMode.HTML
        ); return
    key = context.args[0].strip(); value = " ".join(context.args[1:]).strip()
    await set_runtime_config(key, value)
    await update.message.reply_text("✅ Đã cập nhật: <code>" + html.escape(key) + "</code> = <code>" + html.escape(value) + "</code>", parse_mode=ParseMode.HTML)

async def setprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2: await update.message.reply_text("⚠️ Ví dụ: <code>/setprice deepseek-v4-flash 2</code>", parse_mode=ParseMode.HTML); return
    model = context.args[0].strip()
    try: price = int(context.args[1])
    except ValueError: await update.message.reply_text("❌ Giá phải là số."); return
    await set_model_price(model, price, 1)
    await update.message.reply_text("✅ Đã cập nhật giá: <code>" + html.escape(model) + "</code> = " + str(price) + " req", parse_mode=ParseMode.HTML)

async def admin_models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    prices = await get_model_prices(); text = "🤖 <b>Quản Lý Model:</b>\n\n"
    for k, v in prices.items():
        status = "✅ BẬT" if v["enabled"] else "❌ TẮT"
        text += "• <code>" + html.escape(k) + "</code> | " + str(v['price']) + " req | " + status + "\n"
    text += "\nDùng <code>/togglemodel [tên]</code> để bật/tắt."
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def togglemodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("⚠️ Ví dụ: <code>/togglemodel deepseek-v4-flash</code>", parse_mode=ParseMode.HTML); return
    model = " ".join(context.args).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT enabled FROM model_prices WHERE model_name = ?", (model,))
        row = await cur.fetchone()
        if not row: await update.message.reply_text("❌ Model không tồn tại."); return
        new_state = 0 if row[0] else 1
        await db.execute("UPDATE model_prices SET enabled = ? WHERE model_name = ?", (new_state, model)); await db.commit()
    await update.message.reply_text("✅ Model <code>" + html.escape(model) + "</code> đã " + ('BẬT' if new_state else 'TẮT'), parse_mode=ParseMode.HTML)

async def admin_prompts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    prompts = await get_all_prompts(); text = "🎭 <b>Quản Lý Prompt:</b>\n\n"
    for p in prompts:
        status = "✅ BẬT" if p[2] else "❌ TẮT"
        text += "• <b>" + p[0] + "</b> | " + status + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def addprompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2: await update.message.reply_text("⚠️ Ví dụ: <code>/addprompt funny Bạn là hài hước...</code>", parse_mode=ParseMode.HTML); return
    name = context.args[0].strip().lower(); content = " ".join(context.args[1:]).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO prompts (name, content, enabled) VALUES (?, ?, 1)", (name, content)); await db.commit()
    await update.message.reply_text("✅ Đã thêm prompt: <b>" + name + "</b>", parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("⚠️ Ví dụ: <code>/broadcast Chào tất cả! Có tin mới...</code>", parse_mode=ParseMode.HTML); return
    message = " ".join(context.args); users = await get_all_users(); sent = 0; failed = 0
    for uid in users:
        try: await context.bot.send_message(uid, "📢 <b>Thông Báo Từ Admin:</b>\n\n" + message, parse_mode=ParseMode.HTML); sent += 1; await asyncio.sleep(0.1)
        except Exception: failed += 1
    await update.message.reply_text("✅ Đã gửi: " + str(sent) + " users | ❌ Thất bại: " + str(failed) + " users")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    cfg = await get_all_runtime_config(); current = cfg.get("MAINTENANCE_MODE", "0")
    new_val = "0" if current == "1" else "1"
    await set_runtime_config("MAINTENANCE_MODE", new_val)
    status = "BẬT" if new_val == "1" else "TẮT"
    await update.message.reply_text("🔧 Chế độ bảo trì đã " + status + ".", parse_mode=ParseMode.HTML)

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    status = []
    try:
        async with aiosqlite.connect(DB_PATH) as db: await db.execute("SELECT 1")
        status.append("🟢 Database: OK")
    except Exception as e: status.append("🔴 Database: " + str(e))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(AI_BASE_URL.replace("/v1/chat/completions", "/v1/models"), headers={"Authorization": "Bearer " + AI_API_KEY})
            if r.status_code in [200, 401, 403]: status.append("🟢 AI API: OK")
            else: status.append("🟡 AI API: HTTP " + str(r.status_code))
    except Exception as e: status.append("🔴 AI API: " + str(e))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            import urllib.parse
            test_url = YEUMONEY_API_URL + "?token=" + YEUMONEY_API_KEY + "&url=" + urllib.parse.quote("https://google.com", safe='') + "&format=json"
            r = await client.get(test_url)
            if r.status_code == 200: status.append("🟢 Yeumoney API: OK")
            else: status.append("🟡 Yeumoney API: HTTP " + str(r.status_code))
    except Exception as e: status.append("🔴 Yeumoney API: " + str(e))
    await update.message.reply_text("🏥 <b>System Health Check</b>\n\n" + "\n".join(status), parse_mode=ParseMode.HTML)

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    await auto_cleanup()
    await update.message.reply_text("🧹 Đã dọn dẹp dữ liệu cũ.", parse_mode=ParseMode.HTML)

async def feedback_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    feedbacks = await get_pending_feedback(20)
    if not feedbacks: await update.message.reply_text("✅ Không có feedback nào chờ xử lý."); return
    text = "📣 <b>Feedback Chờ Xử Lý:</b>\n\n"
    for f in feedbacks: text += "#" + str(f[0]) + " | User <code>" + str(f[1]) + "</code> | " + f[4][:16] + "\n" + html.escape(f[3][:200]) + "\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def feedback_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("⚠️ Ví dụ: <code>/feedbackdone 1</code>", parse_mode=ParseMode.HTML); return
    try: fid = int(context.args[0])
    except ValueError: await update.message.reply_text("❌ ID không hợp lệ."); return
    await mark_feedback_done(fid)
    await update.message.reply_text("✅ Đã đánh dấu feedback #" + str(fid) + " đã xử lý.")

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    import csv
    from io import StringIO
    output = StringIO(); writer = csv.writer(output)
    writer.writerow(["user_id", "username", "first_name", "req_balance", "total_keys", "total_messages", "banned", "created_at"])
    users = await get_users_list(limit=10000)
    for u in users: writer.writerow([u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7]])
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8-sig'),
        filename="denia_export_" + datetime.now().strftime('%Y%m%d_%H%M') + ".csv",
        caption="📊 Xuất dữ liệu users thành công."
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception: " + str(context.error))
    if isinstance(update, Update) and update.effective_message:
        try: await update.effective_message.reply_text("❌ Đã xảy ra lỗi. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML)
        except Exception: pass

async def post_init(app: Application):
    user_commands = [
        BotCommand("start", "Menu chính"), BotCommand("help", "Hướng dẫn"),
        BotCommand("key", "Nhập key nhận req"), BotCommand("model", "Chọn model AI"),
        BotCommand("prompt", "Chọn tính cách AI"), BotCommand("new", "Xóa lịch sử chat"),
        BotCommand("history", "Xem lịch sử"), BotCommand("profile", "Hồ sơ cá nhân"),
        BotCommand("top", "Bảng xếp hạng"), BotCommand("checkin", "Điểm danh nhận req"),
        BotCommand("ref", "Mã giới thiệu"), BotCommand("feedback", "Góp ý cho admin"),
    ]
    admin_commands = [
        BotCommand("admin", "Admin Panel"), BotCommand("stats", "Thống kê"), BotCommand("logs", "Xem logs"),
        BotCommand("health", "Kiểm tra hệ thống"), BotCommand("users", "Danh sách users"),
        BotCommand("user", "Chi tiết user"), BotCommand("addreq", "Nạp req"),
        BotCommand("ban", "Khóa user"), BotCommand("unban", "Mở khóa user"),
        BotCommand("config", "Xem cấu hình"), BotCommand("setconfig", "Đổi cấu hình"),
        BotCommand("setprice", "Đổi giá model"), BotCommand("models", "Quản lý model"),
        BotCommand("togglemodel", "Bật/tắt model"), BotCommand("prompts", "Quản lý prompt"),
        BotCommand("addprompt", "Thêm prompt"), BotCommand("broadcast", "Thông báo"),
        BotCommand("maintenance", "Bật/tắt bảo trì"), BotCommand("cleanup", "Dọn dẹp dữ liệu"),
        BotCommand("feedbacklist", "Xem feedback"), BotCommand("feedbackdone", "Xử lý feedback"),
        BotCommand("export", "Xuất CSV"),
    ]
    await app.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    if ADMIN_ID != 0:
        try: await app.bot.set_my_commands(user_commands + admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        except Exception: pass
    logger.info("Bot commands đã được cài đặt.")

def main():
    if not BOT_TOKEN or not AI_API_KEY: logger.error("Thiếu BOT_TOKEN hoặc AI_API_KEY!"); sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("key", key_command)); app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("prompt", prompt_command)); app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("history", history_command)); app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("top", top_command)); app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("ref", ref_command)); app.add_handler(CommandHandler("feedback", feedback_command))

    app.add_handler(CommandHandler("admin", admin_command)); app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("logs", logs_command)); app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("users", users_command)); app.add_handler(CommandHandler("user", user_detail_command))
    app.add_handler(CommandHandler("addreq", addreq_command)); app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command)); app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("setconfig", setconfig_command)); app.add_handler(CommandHandler("setprice", setprice_command))
    app.add_handler(CommandHandler("models", admin_models_command)); app.add_handler(CommandHandler("togglemodel", togglemodel_command))
    app.add_handler(CommandHandler("prompts", admin_prompts_command)); app.add_handler(CommandHandler("addprompt", addprompt_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command)); app.add_handler(CommandHandler("maintenance", maintenance_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command)); app.add_handler(CommandHandler("feedbacklist", feedback_list_command))
    app.add_handler(CommandHandler("feedbackdone", feedback_done_command)); app.add_handler(CommandHandler("export", export_command))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    app.add_error_handler(error_handler)

    logger.info("🚀 Denia AI Bot PRO v2 đang khởi động...")
    asyncio.run(init_db()); asyncio.run(init_model_prices()); asyncio.run(auto_cleanup())
    logger.info("Database & Model Prices đã sẵn sàng.")
    logger.info("Admin: " + ADMIN_PHONE)
    logger.info("Req/link: " + str(REQ_PER_LINK) + " | Max: " + str(MAX_REQ_BALANCE))
    logger.info("Models: " + str(len([k for k in os.environ if k.startswith('PRICE_')])) + " model đã load giá")
    if ADMIN_TELEGRAM_ID == 0: logger.info("Admin auto-set: Người đầu tiên gửi /admin sẽ trở thành admin")
    else: logger.info("Admin ID: " + str(ADMIN_TELEGRAM_ID))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__": main()
