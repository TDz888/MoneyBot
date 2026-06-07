"""
Denia AI Bot - Final Secure Version
Logic: Chi gui link rut gon, KHONG hien thi key trong Telegram.
User vuot Yeumoney -> thay key tren dpaste -> /key ve bot.
"""
import os, sys, random, string, logging, asyncio, html
from datetime import datetime, timedelta
import httpx
import aiosqlite
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
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
        await db.execute("CREATE TABLE IF NOT EXISTS cooldowns (user_id INTEGER PRIMARY KEY, last_chat_at TIMESTAMP)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS model_prices (
                model_name TEXT PRIMARY KEY, req_price INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1
            )""")
        await db.execute("CREATE TABLE IF NOT EXISTS prompts (name TEXT PRIMARY KEY, content TEXT, enabled INTEGER DEFAULT 1)")
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
            await db.execute("INSERT INTO users (user_id, username, first_name, selected_model, referral_code) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, first_name, DEFAULT_MODEL, ref_code))
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
        if row[3]: return (False, "Tai khoan cua ban da bi khoa. Lien he admin.")
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
            await db.execute("UPDATE users SET last_key_at = ?, keys_today = keys_today + 1, last_key_date = ? WHERE user_id = ?",
                (datetime.now().isoformat(), today_str, user_id))
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
        if not row: return {"ok": False, "msg": "Key khong ton tai."}
        key_owner, used, expires_at = row[0], row[1], row[2]
        if used: return {"ok": False, "msg": "Key da duoc su dung."}
        if key_owner != user_id: return {"ok": False, "msg": "Key nay khong thuoc ve ban."}
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
            await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
            await db.commit(); return {"ok": False, "msg": "Key da het han."}
        cur2 = await db.execute("SELECT req_balance FROM users WHERE user_id = ?", (user_id,))
        bal = (await cur2.fetchone())[0] or 0
        if bal + req_per > max_bal: return {"ok": False, "msg": "Ban da dat gioi han " + str(max_bal) + " req."}
        await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
        await db.execute("UPDATE users SET req_balance = req_balance + ?, total_keys_used = total_keys_used + 1 WHERE user_id = ?", (req_per, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "USE_KEY", key_code + " +" + str(req_per) + "req"))
        await db.commit()
        return {"ok": True, "msg": "Key hop le! +" + str(req_per) + " req."}

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

async def create_paste_dpaste(key: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            content_text = "Ma kich hoat Denia AI\n\n" + key + "\n\nCopy ma tren va gui lai bot: /key " + key
            r = await client.post(
                "https://dpaste.com/api/",
                data={"content": content_text, "syntax": "text", "expiry_days": "1"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if r.status_code in [200, 201]:
                url = r.text.strip()
                if url.startswith("http"): return url
    except Exception as e:
        logger.warning("dpaste error: " + str(e))
    return None

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
    except Exception as e:
        logger.warning("Yeumoney API error: " + str(e))
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
            r = await client.post(
                AI_BASE_URL,
                headers={"Authorization": "Bearer " + AI_API_KEY, "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.7}
            )
            data = r.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"]
                await add_conversation(user_id, "user", user_message); await add_conversation(user_id, "assistant", reply); return (reply, req_cost)
            return ("AI khong tra loi. Thu lai sau.", 0)
    except Exception as e:
        logger.error("AI error: " + str(e)); return ("AI dang ban. Vui long thu lai sau.", 0)

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

    if args and len(args) > 0:
        key_input = args[0].strip().upper()
        if key_input.startswith("DENIA-"):
            u = await get_or_create_user(user.id, user.username, user.first_name)
            if u["banned"]:
                await update.message.reply_text("Tai khoan cua ban da bi khoa. Lien he admin.")
                return
            result = await use_key(key_input, user.id)
            if result["ok"]:
                await update.message.reply_text(
                    "Chao mung tro lai!\n\n" + result["msg"] + "\n\n"
                    "Ban co the bat dau chat AI ngay bay gio!\n"
                    "Go /help de xem huong dan chi tiet.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(result["msg"], parse_mode=ParseMode.HTML)
            return
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
                            "Chao mung! Ban duoc moi boi user.\n"
                            "Ca 2 ban deu nhan +" + str(bonus) + " req!",
                            parse_mode=ParseMode.HTML
                        )
                        try:
                            await context.bot.send_message(row[0],
                                "Chuc mung! User da dung ma gioi thieu cua ban.\n"
                                "Ban nhan +" + str(bonus) + " req!", parse_mode=ParseMode.HTML)
                        except Exception: pass
                        return

    u = await get_or_create_user(user.id, user.username, user.first_name)
    if u["banned"]:
        await update.message.reply_text("Tai khoan cua ban da bi khoa. Lien he admin.")
        return

    prices = await get_model_prices()
    price_list = "\n".join(["- " + html.escape(k) + ": " + str(v['price']) + " req" for k, v in prices.items() if v['enabled']])

    keyboard = [
        [InlineKeyboardButton("Nhan Key Moi", callback_data="getkey")],
        [InlineKeyboardButton("Diem Danh", callback_data="checkin"), InlineKeyboardButton("So Du", callback_data="balance")],
        [InlineKeyboardButton("Chon Model", callback_data="models"), InlineKeyboardButton("Tinh Cach", callback_data="prompts")],
        [InlineKeyboardButton("Bang Xep Hang", callback_data="top"), InlineKeyboardButton("Ho Tro", callback_data="support")]
    ]

    await update.message.reply_text(
        "Xin chao " + html.escape(user.first_name or "ban") + "!\n\n"
        "Denia AI Bot - Tro ly AI thong minh, co tri nho!\n\n"
        "So du: " + str(u['req_balance']) + " req\n"
        "Model: " + html.escape(u['selected_model'] or DEFAULT_MODEL) + "\n"
        "Tinh cach: " + str(u['selected_prompt']) + "\n"
        "Gia chat: " + str(get_model_price(u['selected_model'] or DEFAULT_MODEL)) + " req/tin nhan\n\n"
        "Bang gia model:\n" + price_list + "\n\n"
        "Ma gioi thieu: " + str(u['referral_code']) + "\n"
        "Go /help de xem huong dan chi tiet.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Huong Dan Su Dung - Denia AI\n\n"
        "Cach nhan req (3 buoc don gian):\n"
        "1. Nhan 'Nhan Key Moi' tren menu\n"
        "2. Bot tao link rut gon qua Yeumoney\n"
        "3. Copy link -> mo trinh duyet -> vuot -> thay KEY hien ra\n"
        "4. Copy KEY -> gui bot: /key denia-XXXXXX-XX-XXXXXXXXXXXXX-XXX\n"
        "5. Bot cong req ngay lap tuc!\n\n"
        "Lenh nang cao:\n"
        "/model - Chon model AI\n"
        "/prompt - Chon tinh cach AI\n"
        "/new - Xoa lich su chat\n"
        "/history - Xem lich su\n"
        "/profile - Ho so ca nhan\n"
        "/top - Bang xep hang\n"
        "/checkin - Diem danh nhan req\n"
        "/ref - Ma gioi thieu\n"
        "/feedback - Gop y cho admin\n\n"
        "Luu y:\n"
        "- Moi tin nhan AI ton req tuy model (1-5 req)\n"
        "- Nhan key cach nhau 15 phut, toi da 10 key/ngay\n"
        "- Gioi han tich luy: 5000 req\n"
        "- Key het han sau 120 phut neu khong dung\n\n"
        "Ho tro: " + ADMIN_PHONE,
        parse_mode=ParseMode.HTML
    )

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Vui long gui kem ma key.\n"
            "Vi du: /key denia-A1B2C3-D4-E5F6G7H8I9J10-K11",
            parse_mode=ParseMode.HTML
        ); return
    key_input = context.args[0].strip().upper()
    if not key_input.startswith("DENIA-"):
        await update.message.reply_text("Key phai bat dau bang denia-", parse_mode=ParseMode.HTML); return
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
            "Model hien tai: " + html.escape(current) + "\n\n"
            "Chon model ben duoi:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        ); return
    model_name = " ".join(context.args).strip(); found = False
    for k in prices.keys():
        if model_name.lower() in k.lower() or k.lower() in model_name.lower():
            if prices[k]["enabled"]: model_name = k; found = True; break
    if not found: await update.message.reply_text("Model khong hop le hoac da bi tat."); return
    await set_user_model(user_id, model_name)
    await update.message.reply_text(
        "Da chuyen sang model: " + html.escape(model_name) + "\n"
        "Gia: " + str(prices[model_name]['price']) + " req/tin nhan", parse_mode=ParseMode.HTML
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
            "Tinh cach hien tai: " + current + "\n\n"
            "Chon tinh cach ben duoi:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        ); return
    name = context.args[0].strip().lower(); valid = [p[0] for p in prompts if p[2]]
    if name not in valid: await update.message.reply_text("Tinh cach khong hop le. Cac lua chon: " + ", ".join(valid)); return
    await set_user_prompt(user_id, name)
    await update.message.reply_text(
        "Da chuyen sang tinh cach: " + name.upper() + "\n"
        "AI se tra loi theo phong cach moi tu tin nhan tiep theo.", parse_mode=ParseMode.HTML
    )

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await clear_conversation(user_id)
    await update.message.reply_text(
        "Da xoa lich su chat!\n\n"
        "AI khong con nho gi ve cuoc tro chuyen truoc.\n"
        "Ban co the bat dau chu de moi ngay bay gio.", parse_mode=ParseMode.HTML
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hist = await get_conversation_history(user_id, limit=10)
    if not hist: await update.message.reply_text("Chua co lich su chat nao."); return
    text = "Lich su chat gan day:\n\n"
    for msg in hist:
        role = "Ban" if msg["role"] == "user" else "AI"
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
        "Ho so cua ban\n\n"
        "ID: " + str(u['user_id']) + "\n"
        "Ten: " + html.escape(u['first_name'] or 'N/A') + "\n"
        "So du: " + str(u['req_balance']) + " req\n"
        "Da dung: " + str(u['total_keys_used']) + " key\n"
        "Tin nhan: " + str(u['total_messages']) + "\n"
        "Tham gia: " + (u['created_at'][:10] if u['created_at'] else 'N/A') + "\n"
        "Model: " + html.escape(model) + "\n"
        "Tinh cach: " + str(u['selected_prompt']) + "\n"
        "Gia chat: " + str(price) + " req/tin nhan\n"
        "Ma gioi thieu: " + str(u['referral_code']) + "\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = await get_top_users()
    if not top: await update.message.reply_text("Chua co du lieu xep hang."); return
    text = "Bang Xep Hang - Top 10\n\n"
    medals = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    for i, u in enumerate(top):
        name = html.escape(u[1] or u[2] or "User " + str(u[0]))
        text += medals[i] + ". " + name + " - " + str(u[3]) + " tin nhan | " + str(u[4]) + " req\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ok, bonus = await daily_checkin(user_id)
    if ok:
        await update.message.reply_text(
            "Diem danh thanh cong!\n\n"
            "Ban nhan +" + str(bonus) + " req mien phi!\n"
            "Hen gap lai ban vao ngay mai!", parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "Ban da diem danh hom nay roi!\n\n"
            "Hay quay lai vao ngay mai de nhan them req nhe.", parse_mode=ParseMode.HTML
        )

async def ref_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_or_create_user(user_id)
    bonus = int(await get_runtime_config("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
    link = "https://t.me/" + context.bot.username + "?start=" + u['referral_code']
    await update.message.reply_text(
        "Ma gioi thieu cua ban\n\n"
        "Link moi: " + link + "\n\n"
        "Phan thuong: Moi luot moi thanh cong, ca 2 deu nhan +" + str(bonus) + " req!\n"
        "Huong dan: Chia se link ben tren cho ban be. Khi ho nhan Start, ca 2 deu duoc thuong.",
        parse_mode=ParseMode.HTML
    )

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Vui long gui kem noi dung gop y.\n"
            "Vi du: /feedback Bot rat hay, cam on admin!", parse_mode=ParseMode.HTML
        ); return
    content = " ".join(context.args).strip()
    await add_feedback(user_id, content)
    await update.message.reply_text(
        "Cam on ban da gop y!\n\n"
        "Admin se xem xet va phan hoi som nhat.", parse_mode=ParseMode.HTML
    )
    try:
        if ADMIN_ID and ADMIN_ID != 0:
            await context.bot.send_message(ADMIN_ID,
                "Feedback moi tu " + str(user_id) + ":\n" + html.escape(content[:500]),
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
            await query.edit_message_text(msg, parse_mode=ParseMode.HTML); return

        key = generate_key()
        success = await create_key(user_id, key)
        if not success:
            await query.edit_message_text("Loi he thong khi tao key. Vui long thu lai sau.", parse_mode=ParseMode.HTML); return

        paste_url = await create_paste_dpaste(key)
        cfg = await get_all_runtime_config()
        expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))

        if paste_url:
            short_link = await shorten_yeumoney(paste_url)
            if short_link:
                text = (
                    "Link vuot cua ban da san sang!\n\n"
                    "Link rut gon Yeumoney:\n"
                    + html.escape(short_link) + "\n\n"
                    "Huong dan vuot link (3 buoc):\n\n"
                    "1. Copy link ben tren -> mo trinh duyet (Chrome/Safari)\n"
                    "2. Vuot Yeumoney (cho 15-30 giay) -> click Tiep tuc\n"
                    "3. Ban se thay KEY hien thi tren trang -> Copy key\n\n"
                    "Sau khi co key, gui lai bot:\n"
                    "/key [dan-key-vua-copy]\n\n"
                    "Bot se cong " + str(REQ_PER_LINK) + " req ngay lap tuc!\n\n"
                    "Key het han sau: " + str(expire) + " phut\n"
                    "Luu y: Khong thoat khoi trang Yeumoney truoc khi click Tiep tuc"
                )
            else:
                text = (
                    "Bot chua rut gon duoc link.\n\n"
                    "Link goc (ban tu rut gon qua Yeumoney):\n"
                    + html.escape(paste_url) + "\n\n"
                    "Cach lam:\n"
                    "1. Vao yeumoney.com -> rut gon link ben tren\n"
                    "2. Vuot link rut gon -> thay KEY hien thi\n"
                    "3. Copy key -> gui bot: /key [dan-key]\n\n"
                    "Key het han sau: " + str(expire) + " phut"
                )
        else:
            bot_username = context.bot.username or "bot"
            text = (
                "Loi tao link dich.\n\n"
                "Key cua ban: " + key + "\n\n"
                "Vui long tu rut gon link nay qua Yeumoney:\n"
                "https://t.me/" + bot_username + "?start=" + key + "\n\n"
                "Sau khi vuot, nhan Start de bot tu dong nhan key."
            )

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    elif data == "balance":
        u = await get_or_create_user(user_id)
        model = u["selected_model"] or DEFAULT_MODEL
        prices = await get_model_prices(); price = 1
        for k,v in prices.items():
            if k.lower() in model.lower() or model.lower() in k.lower(): price = v["price"]; break
        await query.edit_message_text(
            "So du tai khoan\n\n"
            "Req hien co: " + str(u['req_balance']) + " req\n"
            "Da dung: " + str(u['total_keys_used']) + " key\n"
            "Hom nay: " + str(u['keys_today']) + "/10 key\n"
            "Tin nhan: " + str(u['total_messages']) + "\n"
            "Model: " + html.escape(model) + "\n"
            "Tinh cach: " + str(u['selected_prompt']) + "\n"
            "Gia chat: " + str(price) + " req/tin nhan\n\n"
            "Ma gioi thieu: " + str(u['referral_code']),
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
            "Chon Model AI\n\n"
            "Goi y:\n"
            "- Model 1 req = Nhanh, phu hop chat thuong\n"
            "- Model 3-5 req = Thong minh hon, chuyen sau\n\n"
            "Chon model ben duoi:",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        )

    elif data == "prompts":
        prompts = await get_all_prompts()
        buttons = []
        for name, content, enabled in prompts:
            if enabled: buttons.append([InlineKeyboardButton(name.upper(), callback_data="setprompt|" + name)])
        await query.edit_message_text(
            "Chon Tinh Cach AI\n\n"
            "- DEFAULT: Tro ly can bang, da nang\n"
            "- CREATIVE: Bay bong, giau cam xuc\n"
            "- CODER: Lap trinh vien chuyen nghiep\n"
            "- TEACHER: Giao vien kien nhan\n\n"
            "Chon tinh cach ben duoi:",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        )

    elif data == "support":
        await query.edit_message_text(
            "Ho Tro Denia AI\n\n"
            "Zalo / Telegram: " + ADMIN_PHONE + "\n"
            "Gio ho tro: 08:00 - 22:00 (GMT+7)\n\n"
            "Vui long khong spam tin nhan.\n"
            "Mo ta ro van de de duoc ho tro nhanh nhat.",
            parse_mode=ParseMode.HTML
        )

    elif data == "top":
        top = await get_top_users()
        if not top: await query.edit_message_text("Chua co du lieu xep hang."); return
        text = "Bang Xep Hang - Top 10\n\n"
        for i, u in enumerate(top):
            name = html.escape(u[1] or u[2] or "User " + str(u[0]))
            text += str(i+1) + ". " + name + " - " + str(u[3]) + " tin nhan | " + str(u[4]) + " req\n"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    elif data == "checkin":
        ok, bonus = await daily_checkin(user_id)
        if ok:
            await query.edit_message_text(
                "Diem danh thanh cong!\n\n"
                "Ban nhan +" + str(bonus) + " req mien phi!\n"
                "Hen gap lai ban vao ngay mai!", parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                "Ban da diem danh hom nay roi!\n\n"
                "Hay quay lai vao ngay mai de nhan them req nhe.", parse_mode=ParseMode.HTML
            )

    elif data.startswith("setmodel|"):
        model = data.split("|", 1)[1]
        await set_user_model(user_id, model)
        prices = await get_model_prices(); price = prices.get(model, {}).get("price", 1)
        await query.edit_message_text(
            "Da chuyen model!\n\n"
            "Model: " + html.escape(model) + "\n"
            "Gia: " + str(price) + " req/tin nhan\n\n"
            "Bat dau chat ngay bay gio!", parse_mode=ParseMode.HTML
        )

    elif data.startswith("setprompt|"):
        name = data.split("|", 1)[1]
        await set_user_prompt(user_id, name)
        await query.edit_message_text(
            "Da chuyen tinh cach!\n\n"
            "Tinh cach: " + name.upper() + "\n"
            "AI se tra loi theo phong cach moi tu tin nhan tiep theo.", parse_mode=ParseMode.HTML
        )

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_or_create_user(user_id)
    if u["banned"]: return

    if await is_maintenance() and not is_admin(user_id):
        await update.message.reply_text(
            "Bot dang bao tri.\n\n"
            "Vui long quay lai sau. Ban van co the nhan key va diem danh.", parse_mode=ParseMode.HTML
        ); return

    ok, remain = await check_chat_cooldown(user_id)
    if not ok:
        await update.message.reply_text("Vui long doi " + str(remain) + " giay nua.")
        return

    model = await get_user_model(user_id)
    prices = await get_model_prices(); price = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            if v["enabled"]: price = v["price"]; break
    success = await deduct_req(user_id, price)
    if not success:
        keyboard = [[InlineKeyboardButton("Nhan Key Moi", callback_data="getkey")]]
        await update.message.reply_text(
            "Ban da het req!\n\n"
            "Can " + str(price) + " req de chat model nay.\n"
            "Nhan nut ben duoi de nhan key.",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        ); return

    await update.message.chat.send_action(action="typing")
    try:
        reply, cost = await chat_ai(user_id, update.message.text)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error("Chat handler error: " + str(e))
        await update.message.reply_text("AI dang ban. Vui long thu lai sau.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await auto_set_admin(user_id)
    if not is_admin(user_id):
        await update.message.reply_text("Ban khong co quyen admin.")
        return
    await update.message.reply_text(
        "ADMIN PANEL - Denia AI\n\n"
        "Thong ke:\n"
        "/stats - Xem thong ke tong quan\n"
        "/logs - Xem 50 hoat dong gan nhat\n"
        "/health - Kiem tra he thong\n\n"
        "Quan ly Users:\n"
        "/users - Danh sach users\n"
        "/user [id] - Chi tiet user\n"
        "/addreq [id] [so req] - Nap req\n"
        "/ban [id] - Khoa user\n"
        "/unban [id] - Mo khoa user\n\n"
        "Cau hinh Bot:\n"
        "/config - Xem cau hinh hien tai\n"
        "/setconfig [key] [value] - Doi cau hinh\n"
        "/setprice [model] [gia] - Doi gia model\n"
        "/maintenance - Bat/tat bao tri\n\n"
        "Quan ly Model & Prompt:\n"
        "/models - Quan ly model\n"
        "/togglemodel [model] - Bat/tat model\n"
        "/prompts - Quan ly prompt\n"
        "/addprompt [ten] [noi dung] - Them prompt\n\n"
        "Thong bao & Feedback:\n"
        "/broadcast [tin nhan] - Gui thong bao\n"
        "/feedbacklist - Xem gop y chua doc\n"
        "/feedbackdone [id] - Danh dau da xu ly\n\n"
        "Don dep:\n"
        "/cleanup - Xoa du lieu cu\n"
        "/export - Xuat CSV thong ke\n\n"
        "Admin: " + ADMIN_PHONE,
        parse_mode=ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    stats = await get_stats()
    await update.message.reply_text(
        "Thong Ke Denia AI\n\n"
        "Tong users: " + str(stats['total_users']) + "\n"
        "Tong req luu hanh: " + str(stats['total_req']) + "\n"
        "Key da dung: " + str(stats['total_keys']) + "\n"
        "Key cho xu ly: " + str(stats['pending_keys']) + "\n"
        "Tin nhan AI: " + str(stats['total_messages']) + "\n"
        "Hoat dong hom nay: " + str(stats['today_logs']) + "\n"
        "Feedback cho: " + str(stats['pending_feedback']) + "\n\n"
        "Admin: " + ADMIN_PHONE,
        parse_mode=ParseMode.HTML
    )

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    logs = await get_recent_logs(50)
    text = "Logs Gan Day (50):\n\n"
    for l in logs:
        text += "[" + l[4][:16] + "] " + str(l[0]) + " | " + html.escape(l[1] or 'N/A') + " | " + l[2] + " | " + html.escape(l[3]) + "\n"
    if len(text) > 4000: text = text[:4000] + "\n... (con nhieu)"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    users = await get_users_list(limit=20)
    text = "Danh Sach Users (20 gan nhat):\n\n"
    for u in users:
        status = "BANNED" if u[6] else "OK"
        name = html.escape(u[2] or u[1] or str(u[0]))
        text += str(u[0]) + " | " + name + " | Req: " + str(u[3]) + " | Keys: " + str(u[4]) + " | Msg: " + str(u[5]) + " | " + status + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def user_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args:
        await update.message.reply_text("Vui long nhap user ID. Vi du: /user 123456789", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0])
    except ValueError: await update.message.reply_text("ID khong hop le."); return
    user = await get_or_create_user(target_id); logs = await get_user_logs(target_id, 10)
    text = (
        "Chi Tiet User " + str(target_id) + "\n\n"
        "Username: " + html.escape(user['username'] or 'N/A') + "\n"
        "Ten: " + html.escape(user['first_name'] or 'N/A') + "\n"
        "Req: " + str(user['req_balance']) + "\n"
        "Keys used: " + str(user['total_keys_used']) + "\n"
        "Messages: " + str(user['total_messages']) + "\n"
        "Model: " + html.escape(user['selected_model'] or 'N/A') + "\n"
        "Prompt: " + str(user['selected_prompt']) + "\n"
        "Ma gioi thieu: " + str(user['referral_code']) + "\n"
        "Status: " + ('BANNED' if user['banned'] else 'OK') + "\n"
        "Created: " + str(user['created_at']) + "\n\n"
        "Logs gan day:\n"
    )
    for l in logs: text += "- " + l[2] + " | " + l[0] + " | " + html.escape(l[1]) + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def addreq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2:
        await update.message.reply_text("Vi du: /addreq 123456789 100", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0]); amount = int(context.args[1])
    except ValueError: await update.message.reply_text("So khong hop le."); return
    await admin_add_req(target_id, amount)
    await update.message.reply_text("Da nap " + str(amount) + " req cho user " + str(target_id), parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(target_id,
            "Thong Bao Tu Admin\n\n"
            "Ban vua duoc cong " + str(amount) + " req!\n"
            "So du hien tai da duoc cap nhat.", parse_mode=ParseMode.HTML)
    except Exception: pass

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("Vi du: /ban 123456789", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0])
    except ValueError: await update.message.reply_text("ID khong hop le."); return
    await admin_ban_user(target_id, 1)
    await update.message.reply_text("Da khoa user " + str(target_id), parse_mode=ParseMode.HTML)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("Vi du: /unban 123456789", parse_mode=ParseMode.HTML); return
    try: target_id = int(context.args[0])
    except ValueError: await update.message.reply_text("ID khong hop le."); return
    await admin_ban_user(target_id, 0)
    await update.message.reply_text("Da mo khoa user " + str(target_id), parse_mode=ParseMode.HTML)

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    cfg = await get_all_runtime_config(); text = "Cau Hinh Hien Tai:\n\n"
    for k, v in cfg.items(): text += "- " + html.escape(k) + " = " + html.escape(v) + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def setconfig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Vi du: /setconfig REQ_PER_LINK 300\n"
            "Cac key: REQ_PER_LINK, MAX_REQ_BALANCE, KEY_COOLDOWN_MINUTES, KEY_EXPIRE_MINUTES, MAX_KEYS_PER_DAY, "
            "CHAT_COOLDOWN_SECONDS, MAX_MEMORY_MESSAGES, DAILY_CHECKIN_REQ, REFERRAL_BONUS_REQ, MAINTENANCE_MODE, AUTO_CLEANUP_DAYS",
            parse_mode=ParseMode.HTML
        ); return
    key = context.args[0].strip(); value = " ".join(context.args[1:]).strip()
    await set_runtime_config(key, value)
    await update.message.reply_text("Da cap nhat: " + html.escape(key) + " = " + html.escape(value), parse_mode=ParseMode.HTML)

async def setprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2: await update.message.reply_text("Vi du: /setprice deepseek-v4-flash 2", parse_mode=ParseMode.HTML); return
    model = context.args[0].strip()
    try: price = int(context.args[1])
    except ValueError: await update.message.reply_text("Gia phai la so."); return
    await set_model_price(model, price, 1)
    await update.message.reply_text("Da cap nhat gia: " + html.escape(model) + " = " + str(price) + " req", parse_mode=ParseMode.HTML)

async def admin_models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    prices = await get_model_prices(); text = "Quan Ly Model:\n\n"
    for k, v in prices.items():
        status = "BAT" if v["enabled"] else "TAT"
        text += "- " + html.escape(k) + " | " + str(v['price']) + " req | " + status + "\n"
    text += "\nDung /togglemodel [ten] de bat/tat."
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def togglemodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("Vi du: /togglemodel deepseek-v4-flash", parse_mode=ParseMode.HTML); return
    model = " ".join(context.args).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT enabled FROM model_prices WHERE model_name = ?", (model,))
        row = await cur.fetchone()
        if not row: await update.message.reply_text("Model khong ton tai."); return
        new_state = 0 if row[0] else 1
        await db.execute("UPDATE model_prices SET enabled = ? WHERE model_name = ?", (new_state, model)); await db.commit()
    await update.message.reply_text("Model " + html.escape(model) + " da " + ('BAT' if new_state else 'TAT'), parse_mode=ParseMode.HTML)

async def admin_prompts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    prompts = await get_all_prompts(); text = "Quan Ly Prompt:\n\n"
    for p in prompts:
        status = "BAT" if p[2] else "TAT"
        text += "- " + p[0] + " | " + status + "\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def addprompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if len(context.args) < 2: await update.message.reply_text("Vi du: /addprompt funny Ban la hai huoc...", parse_mode=ParseMode.HTML); return
    name = context.args[0].strip().lower(); content = " ".join(context.args[1:]).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO prompts (name, content, enabled) VALUES (?, ?, 1)", (name, content)); await db.commit()
    await update.message.reply_text("Da them prompt: " + name, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("Vi du: /broadcast Chao tat ca! Co tin moi...", parse_mode=ParseMode.HTML); return
    message = " ".join(context.args); users = await get_all_users(); sent = 0; failed = 0
    for uid in users:
        try: await context.bot.send_message(uid, "Thong Bao Tu Admin:\n\n" + message, parse_mode=ParseMode.HTML); sent += 1; await asyncio.sleep(0.1)
        except Exception: failed += 1
    await update.message.reply_text("Da gui: " + str(sent) + " users | That bai: " + str(failed) + " users")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    cfg = await get_all_runtime_config(); current = cfg.get("MAINTENANCE_MODE", "0")
    new_val = "0" if current == "1" else "1"
    await set_runtime_config("MAINTENANCE_MODE", new_val)
    status = "BAT" if new_val == "1" else "TAT"
    await update.message.reply_text("Che do bao tri da " + status + ".", parse_mode=ParseMode.HTML)

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    status = []
    try:
        async with aiosqlite.connect(DB_PATH) as db: await db.execute("SELECT 1")
        status.append("Database: OK")
    except Exception as e: status.append("Database: " + str(e))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(AI_BASE_URL.replace("/v1/chat/completions", "/v1/models"), headers={"Authorization": "Bearer " + AI_API_KEY})
            if r.status_code in [200, 401, 403]: status.append("AI API: OK")
            else: status.append("AI API: HTTP " + str(r.status_code))
    except Exception as e: status.append("AI API: " + str(e))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            import urllib.parse
            test_url = YEUMONEY_API_URL + "?token=" + YEUMONEY_API_KEY + "&url=" + urllib.parse.quote("https://google.com", safe='') + "&format=json"
            r = await client.get(test_url)
            if r.status_code == 200: status.append("Yeumoney API: OK")
            else: status.append("Yeumoney API: HTTP " + str(r.status_code))
    except Exception as e: status.append("Yeumoney API: " + str(e))
    await update.message.reply_text("System Health Check\n\n" + "\n".join(status), parse_mode=ParseMode.HTML)

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    await auto_cleanup()
    await update.message.reply_text("Da don dep du lieu cu.", parse_mode=ParseMode.HTML)

async def feedback_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    feedbacks = await get_pending_feedback(20)
    if not feedbacks: await update.message.reply_text("Khong co feedback nao cho xu ly."); return
    text = "Feedback Cho Xu Ly:\n\n"
    for f in feedbacks: text += "#" + str(f[0]) + " | User " + str(f[1]) + " | " + f[4][:16] + "\n" + html.escape(f[3][:200]) + "\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def feedback_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    if not context.args: await update.message.reply_text("Vi du: /feedbackdone 1", parse_mode=ParseMode.HTML); return
    try: fid = int(context.args[0])
    except ValueError: await update.message.reply_text("ID khong hop le."); return
    await mark_feedback_done(fid)
    await update.message.reply_text("Da danh dau feedback #" + str(fid) + " da xu ly.")

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
        caption="Xuat du lieu users thanh cong."
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception: " + str(context.error))
    if isinstance(update, Update) and update.effective_message:
        try: await update.effective_message.reply_text("Da xay ra loi. Vui long thu lai sau.", parse_mode=ParseMode.HTML)
        except Exception: pass

async def post_init(app: Application):
    user_commands = [
        BotCommand("start", "Menu chinh"), BotCommand("help", "Huong dan"),
        BotCommand("key", "Nhap key nhan req"), BotCommand("model", "Chon model AI"),
        BotCommand("prompt", "Chon tinh cach AI"), BotCommand("new", "Xoa lich su chat"),
        BotCommand("history", "Xem lich su"), BotCommand("profile", "Ho so ca nhan"),
        BotCommand("top", "Bang xep hang"), BotCommand("checkin", "Diem danh nhan req"),
        BotCommand("ref", "Ma gioi thieu"), BotCommand("feedback", "Gop y cho admin"),
    ]
    admin_commands = [
        BotCommand("admin", "Admin Panel"), BotCommand("stats", "Thong ke"), BotCommand("logs", "Xem logs"),
        BotCommand("health", "Kiem tra he thong"), BotCommand("users", "Danh sach users"),
        BotCommand("user", "Chi tiet user"), BotCommand("addreq", "Nap req"),
        BotCommand("ban", "Khoa user"), BotCommand("unban", "Mo khoa user"),
        BotCommand("config", "Xem cau hinh"), BotCommand("setconfig", "Doi cau hinh"),
        BotCommand("setprice", "Doi gia model"), BotCommand("models", "Quan ly model"),
        BotCommand("togglemodel", "Bat/tat model"), BotCommand("prompts", "Quan ly prompt"),
        BotCommand("addprompt", "Them prompt"), BotCommand("broadcast", "Thong bao"),
        BotCommand("maintenance", "Bat/tat bao tri"), BotCommand("cleanup", "Don dep du lieu"),
        BotCommand("feedbacklist", "Xem feedback"), BotCommand("feedbackdone", "Xu ly feedback"),
        BotCommand("export", "Xuat CSV"),
    ]
    await app.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    if ADMIN_ID != 0:
        try: await app.bot.set_my_commands(user_commands + admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        except Exception: pass
    logger.info("Bot commands da duoc cai dat.")

def main():
    if not BOT_TOKEN or not AI_API_KEY: logger.error("Thieu BOT_TOKEN hoac AI_API_KEY!"); sys.exit(1)
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

    logger.info("Denia AI Bot PRO v3 dang khoi dong...")
    asyncio.run(init_db()); asyncio.run(init_model_prices()); asyncio.run(auto_cleanup())
    logger.info("Database & Model Prices da san sang.")
    logger.info("Admin: " + ADMIN_PHONE)
    logger.info("Req/link: " + str(REQ_PER_LINK) + " | Max: " + str(MAX_REQ_BALANCE))
    logger.info("Models: " + str(len([k for k in os.environ if k.startswith('PRICE_')])) + " model da load gia")
    if ADMIN_TELEGRAM_ID == 0: logger.info("Admin auto-set: Nguoi dau tien gui /admin se tro thanh admin")
    else: logger.info("Admin ID: " + str(ADMIN_TELEGRAM_ID))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__": main()
