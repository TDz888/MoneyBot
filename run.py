"""
🤖 DENIA AI BOT - ULTIMATE EDITION
Professional | Secure | Transparent | Feature-Rich
"""
import os, sys, random, string, logging, asyncio, html as html_module
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import httpx
import aiosqlite
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ========================
# CONFIGURATION
# ========================
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
SYSTEM_PROMPT_DEFAULT = os.getenv("SYSTEM_PROMPT_DEFAULT", "Ban la Denia AI, mot tro ly thong minh, than thien, huu ich. Tra loi ngan gon, ro rang, dung Markdown khi can.").strip()
DAILY_CHECKIN_REQ = int(os.getenv("DAILY_CHECKIN_REQ", "20"))
REFERRAL_BONUS_REQ = int(os.getenv("REFERRAL_BONUS_REQ", "50"))
MAINTENANCE_MODE = int(os.getenv("MAINTENANCE_MODE", "0"))
AUTO_CLEANUP_DAYS = int(os.getenv("AUTO_CLEANUP_DAYS", "7"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("DeniaBot")

DB_PATH = os.path.join(os.path.dirname(__file__), "denia_ultimate.db")
ADMIN_ID = ADMIN_TELEGRAM_ID

MODEL_PRICES: Dict[str, int] = {}
for k, v in os.environ.items():
    if k.startswith("PRICE_"):
        mk = k[6:].replace("_", "-").replace("--", "/")
        MODEL_PRICES[mk] = int(v)

# ========================
# DATABASE
# ========================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                req_balance INTEGER DEFAULT 0,
                total_keys_used INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                last_key_at TEXT,
                keys_today INTEGER DEFAULT 0,
                last_key_date TEXT,
                selected_model TEXT,
                selected_prompt TEXT DEFAULT 'default',
                banned INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                daily_checkin_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                key_code TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_keys_user ON keys(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_keys_used ON keys(used)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
        await db.execute("CREATE TABLE IF NOT EXISTS cooldowns (user_id INTEGER PRIMARY KEY, last_chat_at TEXT)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                detail TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_user ON logs(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_date ON logs(created_at)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS model_prices (
                model_name TEXT PRIMARY KEY,
                req_price INTEGER DEFAULT 1,
                enabled INTEGER DEFAULT 1
            )""")
        await db.execute("CREATE TABLE IF NOT EXISTS prompts (name TEXT PRIMARY KEY, content TEXT, enabled INTEGER DEFAULT 1)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS runtime_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                bonus_given INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

async def get_cfg(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM runtime_config WHERE key = ?", (key,))
        r = await cur.fetchone()
        return r[0] if r else default

async def set_cfg(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO runtime_config (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()))
        await db.commit()

async def get_all_cfg() -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT key, value FROM runtime_config")
        return {k: v for k, v in await cur.fetchall()}

async def get_user(user_id: int, username: str = None, first_name: str = None) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            ref = "REF" + str(user_id) + str(random.randint(1000, 9999))
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, selected_model, referral_code) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, first_name, DEFAULT_MODEL, ref))
            await db.commit()
            return {
                "user_id": user_id, "username": username, "first_name": first_name,
                "req_balance": 0, "total_keys_used": 0, "total_messages": 0,
                "last_key_at": None, "keys_today": 0, "last_key_date": None,
                "selected_model": DEFAULT_MODEL, "selected_prompt": "default",
                "banned": 0, "referral_code": ref, "referred_by": None,
                "daily_checkin_date": None, "created_at": datetime.now().isoformat()
            }
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

async def can_create_key(user_id: int) -> Tuple[bool, str]:
    cfg = await get_all_cfg()
    cooldown = int(cfg.get("KEY_COOLDOWN_MINUTES", KEY_COOLDOWN_MINUTES))
    max_day = int(cfg.get("MAX_KEYS_PER_DAY", MAX_KEYS_PER_DAY))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_key_at, keys_today, last_key_date, banned FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return True, ""
        if row[3]:
            return False, "🚫 Tài khoản của bạn đã bị khóa. Liên hệ admin."
        last_key_at, keys_today, last_key_date = row[0], row[1] or 0, row[2]
        today_str = datetime.now().strftime("%Y-%m-%d")
        if last_key_date != today_str:
            await db.execute("UPDATE users SET keys_today = 0, last_key_date = ? WHERE user_id = ?", (today_str, user_id))
            await db.commit()
            keys_today = 0
        if keys_today >= max_day:
            return False, f"⏳ Bạn đã nhận đủ {max_day} key hôm nay. Quay lại ngày mai!"
        if last_key_at:
            try:
                last = datetime.fromisoformat(last_key_at)
                diff_sec = (datetime.now() - last).total_seconds()
                if diff_sec < cooldown * 60:
                    remain = int((cooldown * 60 - diff_sec) // 60)
                    if remain < 1:
                        remain = 1
                    return False, f"⏳ Vui lòng đợi {remain} phút nữa để nhận key tiếp."
            except Exception:
                pass
        return True, ""

async def create_key(user_id: int, key_code: str) -> bool:
    cfg = await get_all_cfg()
    expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            exp = datetime.now() + timedelta(minutes=expire)
            await db.execute("INSERT INTO keys (key_code, user_id, expires_at) VALUES (?, ?, ?)", (key_code, user_id, exp.isoformat()))
            today_str = datetime.now().strftime("%Y-%m-%d")
            await db.execute(
                "UPDATE users SET last_key_at = ?, keys_today = keys_today + 1, last_key_date = ? WHERE user_id = ?",
                (datetime.now().isoformat(), today_str, user_id))
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"create_key error: {e}")
            return False

async def use_key(key_code: str, user_id: int) -> Dict[str, Any]:
    cfg = await get_all_cfg()
    req_per = int(cfg.get("REQ_PER_LINK", REQ_PER_LINK))
    max_bal = int(cfg.get("MAX_REQ_BALANCE", MAX_REQ_BALANCE))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, used, expires_at FROM keys WHERE key_code = ?", (key_code,))
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "msg": "❌ Key không tồn tại trong hệ thống."}
        key_owner, used, expires_at = row[0], row[1], row[2]
        if used:
            return {"ok": False, "msg": "❌ Key đã được sử dụng trước đó."}
        if key_owner != user_id:
            return {"ok": False, "msg": "❌ Key này không thuộc về bạn. Mỗi key chỉ dùng cho người tạo ra nó."}
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.now():
                    await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
                    await db.commit()
                    return {"ok": False, "msg": "⏳ Key đã hết hạn. Vui lòng nhận key mới."}
            except Exception:
                pass
        cur2 = await db.execute("SELECT req_balance FROM users WHERE user_id = ?", (user_id,))
        bal = (await cur2.fetchone())[0] or 0
        if bal + req_per > max_bal:
            return {"ok": False, "msg": f"💎 Bạn đã đạt giới hạn tích lũy {max_bal} req. Hãy sử dụng bớt req trước khi nhận thêm."}
        await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
        await db.execute(
            "UPDATE users SET req_balance = req_balance + ?, total_keys_used = total_keys_used + 1 WHERE user_id = ?",
            (req_per, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, "USE_KEY", f"{key_code} +{req_per}req"))
        await db.commit()
        return {"ok": True, "msg": f"✅ Key hợp lệ! +{req_per} req đã được cộng vào tài khoản."}

async def deduct_req(user_id: int, amount: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT req_balance, banned FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row or row[1] or (row[0] or 0) < amount:
            return False
        await db.execute(
            "UPDATE users SET req_balance = req_balance - ?, total_messages = total_messages + 1 WHERE user_id = ?",
            (amount, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, "CHAT", f"-{amount}req"))
        await db.commit()
        return True

async def check_chat_cooldown(user_id: int) -> Tuple[bool, int]:
    cfg = await get_all_cfg()
    cd = int(cfg.get("CHAT_COOLDOWN_SECONDS", CHAT_COOLDOWN_SECONDS))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_chat_at FROM cooldowns WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row and row[0]:
            try:
                last = datetime.fromisoformat(row[0])
                diff = (datetime.now() - last).total_seconds()
                if diff < cd:
                    return False, int(cd - diff)
            except Exception:
                pass
        await db.execute("INSERT OR REPLACE INTO cooldowns (user_id, last_chat_at) VALUES (?, ?)",
            (user_id, datetime.now().isoformat()))
        await db.commit()
        return True, 0

async def set_user_model(user_id: int, model: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model, user_id))
        await db.commit()

async def get_user_model(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT selected_model FROM users WHERE user_id = ?", (user_id,))
        r = await cur.fetchone()
        return r[0] if r and r[0] else DEFAULT_MODEL

async def set_user_prompt(user_id: int, prompt_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET selected_prompt = ? WHERE user_id = ?", (prompt_name, user_id))
        await db.commit()

async def get_user_prompt(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT selected_prompt FROM users WHERE user_id = ?", (user_id,))
        r = await cur.fetchone()
        return r[0] if r and r[0] else "default"

async def get_prompt_content(name: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT content FROM prompts WHERE name = ? AND enabled = 1", (name,))
        r = await cur.fetchone()
        return r[0] if r else SYSTEM_PROMPT_DEFAULT

async def get_all_prompts() -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, content, enabled FROM prompts")
        return await cur.fetchall()

async def add_conversation(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        cfg = await get_all_cfg()
        mm = int(cfg.get("MAX_MEMORY_MESSAGES", MAX_MEMORY_MESSAGES))
        cur = await db.execute("SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, 1000, mm))
        rows = await cur.fetchall()
        if rows:
            ids = ",".join([str(r[0]) for r in rows])
            await db.execute(f"DELETE FROM conversations WHERE id IN ({ids})")
        await db.commit()

async def get_conversation_history(user_id: int, limit: int = None) -> List[Dict[str, str]]:
    if limit is None:
        cfg = await get_all_cfg()
        limit = int(cfg.get("MAX_MEMORY_MESSAGES", MAX_MEMORY_MESSAGES))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT role, content FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit))
        rows = await cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def clear_conversation(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_model_prices() -> Dict[str, Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT model_name, req_price, enabled FROM model_prices")
        rows = await cur.fetchall()
        return {r[0]: {"price": r[1], "enabled": r[2]} for r in rows}

async def set_model_price(model_name: str, price: int, enabled: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO model_prices (model_name, req_price, enabled) VALUES (?, ?, ?)", (model_name, price, enabled))
        await db.commit()

async def init_model_prices():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM model_prices")
        if (await cur.fetchone())[0] == 0:
            for k, v in os.environ.items():
                if k.startswith("PRICE_"):
                    mn = k[6:].replace("_", "-").replace("--", "/")
                    await db.execute("INSERT INTO model_prices (model_name, req_price, enabled) VALUES (?, ?, ?)", (mn, int(v), 1))
            await db.commit()

async def get_stats() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        tu = (await cur.fetchone())[0]
        cur = await db.execute("SELECT SUM(req_balance) FROM users")
        tr = (await cur.fetchone())[0] or 0
        cur = await db.execute("SELECT COUNT(*) FROM keys WHERE used = 1")
        tk = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM keys WHERE used = 0")
        pk = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM conversations")
        tm = (await cur.fetchone())[0]
        today = datetime.now().strftime("%Y-%m-%d")
        cur = await db.execute("SELECT COUNT(*) FROM logs WHERE DATE(created_at) = ?", (today,))
        tl = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM feedback WHERE status = 'pending'")
        pf = (await cur.fetchone())[0]
        return {"total_users": tu, "total_req": tr, "total_keys": tk, "pending_keys": pk,
                "total_messages": tm, "today_logs": tl, "pending_feedback": pf}

async def get_users_list(limit: int = 50, offset: int = 0) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, username, first_name, req_balance, total_keys_used, total_messages, banned, created_at, selected_model, selected_prompt
            FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?""", (limit, offset))
        return await cur.fetchall()

async def get_top_users() -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, first_name, username, total_messages, req_balance
            FROM users ORDER BY total_messages DESC LIMIT 10""")
        return await cur.fetchall()

async def admin_add_req(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET req_balance = req_balance + ? WHERE user_id = ?", (amount, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "ADMIN_ADD", f"+{amount}req"))
        await db.commit()

async def admin_ban_user(user_id: int, ban: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned = ? WHERE user_id = ?", (ban, user_id))
        await db.commit()

async def get_user_logs(user_id: int, limit: int = 20) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT action, detail, created_at FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return await cur.fetchall()

async def get_recent_logs(limit: int = 50) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT l.user_id, u.username, l.action, l.detail, l.created_at
            FROM logs l LEFT JOIN users u ON l.user_id = u.user_id ORDER BY l.id DESC LIMIT ?""", (limit,))
        return await cur.fetchall()

async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]

async def add_feedback(user_id: int, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO feedback (user_id, content) VALUES (?, ?)", (user_id, content))
        await db.commit()

async def get_pending_feedback(limit: int = 20) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT f.id, f.user_id, u.username, f.content, f.created_at
            FROM feedback f LEFT JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'pending' ORDER BY f.id DESC LIMIT ?""", (limit,))
        return await cur.fetchall()

async def mark_feedback_done(feedback_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE feedback SET status = 'done' WHERE id = ?", (feedback_id,))
        await db.commit()

async def check_referral(referrer_id: int, referred_id: int) -> bool:
    if referrer_id == referred_id:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,))
        if await cur.fetchone():
            return False
        await db.execute("INSERT INTO referrals (referrer_id, referred_id, bonus_given) VALUES (?, ?, 1)", (referrer_id, referred_id))
        bonus = int(await get_cfg("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
        await db.execute("UPDATE users SET req_balance = req_balance + ? WHERE user_id = ?", (bonus, referrer_id))
        await db.execute("UPDATE users SET req_balance = req_balance + ? WHERE user_id = ?", (bonus, referred_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (referred_id, "REFERRAL", f"Invited by {referrer_id}, +{bonus}req"))
        await db.commit()
        return True

async def daily_checkin(user_id: int) -> Tuple[bool, int]:
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT daily_checkin_date, req_balance FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return False, 0
        if row[0] == today:
            return False, 0
        bonus = int(await get_cfg("DAILY_CHECKIN_REQ", str(DAILY_CHECKIN_REQ)))
        await db.execute("UPDATE users SET daily_checkin_date = ?, req_balance = req_balance + ? WHERE user_id = ?", (today, bonus, user_id))
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, "CHECKIN", f"+{bonus}req"))
        await db.commit()
        return True, bonus

async def auto_cleanup():
    days = int(await get_cfg("AUTO_CLEANUP_DAYS", str(AUTO_CLEANUP_DAYS)))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM logs WHERE created_at < ?", (cutoff,))
        await db.execute("DELETE FROM keys WHERE used = 0 AND created_at < ?", (cutoff,))
        await db.execute("DELETE FROM conversations WHERE created_at < ?", (cutoff,))
        await db.commit()
        logger.info(f"Cleanup done (> {days} days)")

# ========================
# SERVICES
# ========================
def generate_key() -> str:
    p1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    p2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=2))
    p3 = "".join(random.choices(string.ascii_uppercase + string.digits, k=13))
    p4 = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"denia-{p1}-{p2}-{p3}-{p4}"

async def create_paste_dpaste(key: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            content_text = f"Ma kich hoat Denia AI\n\n{key}\n\nCopy ma tren va gui lai bot: /key {key}"
            r = await client.post(
                "https://dpaste.com/api/",
                data={"content": content_text, "syntax": "text", "expiry_days": "1"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if r.status_code in [200, 201]:
                url = r.text.strip()
                if url.startswith("http"):
                    return url
    except Exception as e:
        logger.warning(f"dpaste error: {e}")
    return None

async def shorten_yeumoney(long_url: str) -> Optional[str]:
    if not YEUMONEY_API_KEY or not YEUMONEY_API_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            import urllib.parse
            encoded = urllib.parse.quote(long_url, safe="")
            api_call = f"{YEUMONEY_API_URL}?token={YEUMONEY_API_KEY}&url={encoded}&format=json"
            r = await client.get(api_call)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success" and "shortenedUrl" in data:
                    return data["shortenedUrl"]
                logger.warning(f"Yeumoney response: {data}")
    except Exception as e:
        logger.warning(f"Yeumoney error: {e}")
    return None

async def chat_ai(user_id: int, user_message: str) -> Tuple[str, int]:
    model = await get_user_model(user_id)
    prices = await get_model_prices()
    req_cost = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            if v["enabled"]:
                req_cost = v["price"]
            break
    prompt_name = await get_user_prompt(user_id)
    system_prompt = await get_prompt_content(prompt_name)
    history = await get_conversation_history(user_id)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                AI_BASE_URL,
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.7}
            )
            data = r.json()
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"]
                await add_conversation(user_id, "user", user_message)
                await add_conversation(user_id, "assistant", reply)
                return reply, req_cost
            return "❌ AI không trả lời. Vui lòng thử lại sau.", 0
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "❌ AI đang bận. Vui lòng thử lại sau ít phút.", 0

def get_model_price(model: str) -> int:
    mk = model.replace("/", "-").lower()
    for k, v in MODEL_PRICES.items():
        if k.lower() in mk or mk in k.lower():
            return v
    return 1

# ========================
# SECURITY & ADMIN
# ========================
ADMIN_ID = ADMIN_TELEGRAM_ID

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID if ADMIN_ID else False

async def auto_set_admin(user_id: int):
    global ADMIN_ID
    if ADMIN_ID == 0:
        ADMIN_ID = user_id
        logger.info(f"Auto-set admin: {user_id}")

async def is_maintenance() -> bool:
    cfg = await get_all_cfg()
    return cfg.get("MAINTENANCE_MODE", str(MAINTENANCE_MODE)) == "1"

# ========================
# USER HANDLERS
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if args and len(args) > 0:
        arg = args[0].strip().upper()
        if arg.startswith("DENIA-"):
            u = await get_user(user.id, user.username, user.first_name)
            if u["banned"]:
                await update.message.reply_text("🚫 Tài khoản của bạn đã bị khóa. Vui lòng liên hệ admin.")
                return
            result = await use_key(arg, user.id)
            if result["ok"]:
                await update.message.reply_text(
                    f"🎉 Chào mừng trở lại!\n\n{result['msg']}\n\n"
                    f"✨ Bạn có thể bắt đầu chat AI ngay bây giờ!\n"
                    f"💡 Gõ /help để xem hướng dẫn chi tiết.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(f"⚠️ {result['msg']}", parse_mode=ParseMode.HTML)
            return
        elif arg.startswith("REF"):
            u = await get_user(user.id, user.username, user.first_name)
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM users WHERE referral_code = ?", (arg,))
                row = await cur.fetchone()
                if row and row[0] != user.id and not u.get("referred_by"):
                    if await check_referral(row[0], user.id):
                        bonus = int(await get_cfg("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
                        await update.message.reply_text(
                            f"🎉 Chào mừng! Bạn được mời bởi user <code>{row[0]}</code>.\n"
                            f"💎 Cả 2 bạn đều nhận +{bonus} req!",
                            parse_mode=ParseMode.HTML
                        )
                        try:
                            await context.bot.send_message(
                                row[0],
                                f"🎉 Chúc mừng! User <code>{user.id}</code> đã dùng mã giới thiệu của bạn.\n"
                                f"💎 Bạn nhận +{bonus} req!",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception:
                            pass
                        return

    u = await get_user(user.id, user.username, user.first_name)
    if u["banned"]:
        await update.message.reply_text("🚫 Tài khoản của bạn đã bị khóa. Vui lòng liên hệ admin.")
        return

    prices = await get_model_prices()
    price_list = "\n".join([f"• <code>{html_module.escape(k)}</code>: {v['price']} req" for k, v in prices.items() if v["enabled"]])

    keyboard = [
        [InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")],
        [InlineKeyboardButton("📅 Điểm Danh", callback_data="checkin"), InlineKeyboardButton("💎 Số Dư", callback_data="balance")],
        [InlineKeyboardButton("🤖 Chọn Model", callback_data="models"), InlineKeyboardButton("🎭 Tính Cách", callback_data="prompts")],
        [InlineKeyboardButton("🏆 Bảng Xếp Hạng", callback_data="top"), InlineKeyboardButton("📞 Hỗ Trợ", callback_data="support")]
    ]

    await update.message.reply_text(
        f"👋 <b>Xin chào {html_module.escape(user.first_name or 'bạn')}!</b>\n\n"
        f"🤖 <b>Denia AI Bot</b> — Trợ lý AI thông minh, có trí nhớ!\n\n"
        f"💎 <b>Số dư:</b> <code>{u['req_balance']} req</code>\n"
        f"⚙️ <b>Model:</b> <code>{html_module.escape(u.get('selected_model') or DEFAULT_MODEL)}</code>\n"
        f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
        f"💰 <b>Giá chat:</b> <code>{get_model_price(u.get('selected_model') or DEFAULT_MODEL)} req</code>/tin nhắn\n\n"
        f"<b>📋 Bảng giá model:</b>\n{price_list}\n\n"
        f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>\n"
        f"💡 Gõ /help để xem hướng dẫn chi tiết.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>Hướng Dẫn Sử Dụng — Denia AI</b>\n\n"
        "<b>🎯 Cách nhận req (3 bước đơn giản):</b>\n"
        "1️⃣ Nhấn <b>🔑 Nhận Key Mới</b> trên menu\n"
        "2️⃣ Bot tạo link rút gọn qua Yeumoney\n"
        "3️⃣ <b>Copy link</b> → mở trình duyệt → vượt → thấy <b>KEY</b> hiện ra\n"
        "4️⃣ Copy KEY → gửi bot: <code>/key denia-XXXXXX-XX-XXXXXXXXXXXXX-XXX</code>\n"
        "5️⃣ Bot cộng req ngay lập tức!\n\n"
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
        "• Nhận key cách nhau 15 phút, tối đa 10/ngày\n"
        "• Giới hạn tích lũy: 5000 req\n"
        "• Key hết hạn sau 120 phút nếu không dùng\n\n"
        f"📞 <b>Hỗ trợ:</b> {ADMIN_PHONE}",
        parse_mode=ParseMode.HTML
    )

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "⚠️ Vui lòng gửi kèm mã key.\n"
            "Ví dụ: <code>/key denia-A1B2C3-D4-E5F6G7H8I9J10-K11</code>",
            parse_mode=ParseMode.HTML
        )
        return
    key_input = context.args[0].strip().upper()
    if not key_input.startswith("DENIA-"):
        await update.message.reply_text("❌ Key phải bắt đầu bằng <code>denia-</code>", parse_mode=ParseMode.HTML)
        return
    result = await use_key(key_input, user_id)
    await update.message.reply_text(result["msg"], parse_mode=ParseMode.HTML)

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prices = await get_model_prices()
    if not context.args:
        current = await get_user_model(user_id)
        buttons = []
        row = []
        for k, v in prices.items():
            if v["enabled"]:
                row.append(InlineKeyboardButton(f"{k[:18]} ({v['price']}r)", callback_data=f"sm|{k}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
        if row:
            buttons.append(row)
        await update.message.reply_text(
            f"⚙️ <b>Model hiện tại:</b> <code>{html_module.escape(current)}</code>\n\n"
            f"Chọn model bên dưới:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return
    model_name = " ".join(context.args).strip()
    found = False
    for k in prices.keys():
        if model_name.lower() in k.lower() or k.lower() in model_name.lower():
            if prices[k]["enabled"]:
                model_name = k
                found = True
                break
    if not found:
        await update.message.reply_text("❌ Model không hợp lệ hoặc đã bị tắt.")
        return
    await set_user_model(user_id, model_name)
    await update.message.reply_text(
        f"✅ Đã chuyển sang model: <code>{html_module.escape(model_name)}</code>\n"
        f"💰 Giá: {prices[model_name]['price']} req/tin nhắn",
        parse_mode=ParseMode.HTML
    )

async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompts = await get_all_prompts()
    if not context.args:
        current = await get_user_prompt(user_id)
        buttons = []
        for name, content, enabled in prompts:
            if enabled:
                buttons.append([InlineKeyboardButton(name.upper(), callback_data=f"sp|{name}")])
        await update.message.reply_text(
            f"🎭 <b>Tính cách hiện tại:</b> <code>{current}</code>\n\n"
            f"Chọn tính cách bên dưới:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return
    name = context.args[0].strip().lower()
    valid = [p[0] for p in prompts if p[2]]
    if name not in valid:
        await update.message.reply_text(f"❌ Tính cách không hợp lệ. Các lựa chọn: {', '.join(valid)}")
        return
    await set_user_prompt(user_id, name)
    await update.message.reply_text(
        f"🎭 Đã chuyển sang tính cách: <b>{name.upper()}</b>\n"
        f"AI sẽ trả lời theo phong cách mới từ tin nhắn tiếp theo.",
        parse_mode=ParseMode.HTML
    )

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await clear_conversation(user_id)
    await update.message.reply_text(
        "🧠 <b>Đã xóa lịch sử chat!</b>\n\n"
        "AI không còn nhớ gì về cuộc trò chuyện trước.\n"
        "Bạn có thể bắt đầu chủ đề mới ngay bây giờ.",
        parse_mode=ParseMode.HTML
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hist = await get_conversation_history(user_id, limit=10)
    if not hist:
        await update.message.reply_text("📝 Chưa có lịch sử chat nào.")
        return
    text = "📝 <b>Lịch sử chat gần đây:</b>\n\n"
    for msg in hist:
        role = "👤 Bạn" if msg["role"] == "user" else "🤖 AI"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        text += f"{role}: {html_module.escape(content)}\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_user(user_id)
    model = u.get("selected_model") or DEFAULT_MODEL
    prices = await get_model_prices()
    price = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            price = v["price"]
            break
    await update.message.reply_text(
        f"👤 <b>Hồ sơ của bạn</b>\n\n"
        f"🆔 <b>ID:</b> <code>{u['user_id']}</code>\n"
        f"👤 <b>Tên:</b> {html_module.escape(u.get('first_name') or 'N/A')}\n"
        f"💎 <b>Số dư:</b> <code>{u.get('req_balance', 0)} req</code>\n"
        f"🔑 <b>Đã dùng:</b> {u.get('total_keys_used', 0)} key\n"
        f"💬 <b>Tin nhắn:</b> {u.get('total_messages', 0)}\n"
        f"📅 <b>Tham gia:</b> {u.get('created_at', 'N/A')[:10]}\n"
        f"⚙️ <b>Model:</b> <code>{html_module.escape(model)}</code>\n"
        f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
        f"💰 <b>Giá chat:</b> {price} req/tin nhắn\n"
        f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>\n",
        parse_mode=ParseMode.HTML
    )

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = await get_top_users()
    if not top:
        await update.message.reply_text("🏆 Chưa có dữ liệu xếp hạng.")
        return
    text = "🏆 <b>Bảng Xếp Hạng — Top 10</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, u in enumerate(top):
        name = html_module.escape(u[1] or u[2] or f"User {u[0]}")
        text += f"{medals[i]} <b>{name}</b> — {u[3]} tin nhắn | {u[4]} req\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ok, bonus = await daily_checkin(user_id)
    if ok:
        await update.message.reply_text(
            f"📅 <b>Điểm danh thành công!</b>\n\n"
            f"🎉 Bạn nhận +{bonus} req miễn phí!\n"
            f"🌟 Hẹn gặp lại bạn vào ngày mai!",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "⚠️ <b>Bạn đã điểm danh hôm nay rồi!</b>\n\n"
            "🌅 Hãy quay lại vào ngày mai để nhận thêm req nhé.",
            parse_mode=ParseMode.HTML
        )

async def ref_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_user(user_id)
    bonus = int(await get_cfg("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
    link = f"https://t.me/{context.bot.username}?start={u.get('referral_code', '')}"
    await update.message.reply_text(
        f"🎁 <b>Mã giới thiệu của bạn</b>\n\n"
        f"🔗 <b>Link mời:</b> <code>{link}</code>\n\n"
        f"💎 <b>Phần thưởng:</b> Mỗi lượt mời thành công, cả 2 đều nhận +{bonus} req!\n"
        f"📤 <b>Hướng dẫn:</b> Chia sẻ link bên trên cho bạn bè. Khi họ nhấn Start, cả 2 đều được thưởng.",
        parse_mode=ParseMode.HTML
    )

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "📣 Vui lòng gửi kèm nội dung góp ý.\n"
            "Ví dụ: <code>/feedback Bot rất hay, cảm ơn admin!</code>",
            parse_mode=ParseMode.HTML
        )
        return
    content = " ".join(context.args).strip()
    await add_feedback(user_id, content)
    await update.message.reply_text(
        "✅ <b>Cảm ơn bạn đã góp ý!</b>\n\n"
        "Admin sẽ xem xét và phản hồi sớm nhất.",
        parse_mode=ParseMode.HTML
    )
    try:
        if ADMIN_ID and ADMIN_ID != 0:
            await context.bot.send_message(
                ADMIN_ID,
                f"📣 <b>Feedback mới từ</b> <code>{user_id}</code>:\n{html_module.escape(content[:500])}",
                parse_mode=ParseMode.HTML
            )
    except Exception:
        pass

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_user(user_id)
    model = u.get("selected_model") or DEFAULT_MODEL
    prices = await get_model_prices()
    price = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            price = v["price"]
            break
    await update.message.reply_text(
        f"💎 <b>Số dư tài khoản</b>\n\n"
        f"💰 <b>Req hiện có:</b> <code>{u.get('req_balance', 0)} req</code>\n"
        f"🔑 <b>Key đã dùng:</b> {u.get('total_keys_used', 0)}\n"
        f"📅 <b>Hôm nay:</b> {u.get('keys_today', 0)}/10 key\n"
        f"💬 <b>Tin nhắn:</b> {u.get('total_messages', 0)}\n"
        f"⚙️ <b>Model:</b> <code>{html_module.escape(model)}</code>\n"
        f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
        f"💰 <b>Giá chat:</b> {price} req/tin nhắn\n\n"
        f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>",
        parse_mode=ParseMode.HTML
    )

# ========================
# CALLBACK HANDLER
# ========================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "getkey":
        ok, msg = await can_create_key(user_id)
        if not ok:
            await query.edit_message_text(f"⚠️ {msg}", parse_mode=ParseMode.HTML)
            return

        key = generate_key()
        if not await create_key(user_id, key):
            await query.edit_message_text("❌ Lỗi hệ thống khi tạo key. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML)
            return

        paste_url = await create_paste_dpaste(key)
        cfg = await get_all_cfg()
        expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))

        if paste_url:
            short_link = await shorten_yeumoney(paste_url)
            if short_link:
                text = (
                    f"🔐 <b>Link vượt của bạn đã sẵn sàng!</b>\n\n"
                    f"🔗 <b>Link rút gọn Yeumoney:</b>\n"
                    f"<code>{html_module.escape(short_link)}</code>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📋 <b>Hướng dẫn vượt link (3 bước):</b>\n\n"
                    f"1️⃣ <b>Copy link</b> bên trên → mở <b>trình duyệt</b> (Chrome/Safari)\n"
                    f"2️⃣ Vượt Yeumoney (chờ 15-30 giây) → Click <b>Tiếp tục</b>\n"
                    f"3️⃣ Bạn sẽ thấy <b>KEY</b> hiển thị trên trang → <b>Copy key</b>\n\n"
                    f"✏️ <b>Sau khi có key, gửi lại bot:</b>\n"
                    f"<code>/key [dán-key-vừa-copy]</code>\n\n"
                    f"💎 Bot sẽ cộng <b>{REQ_PER_LINK} req</b> ngay lập tức!\n\n"
                    f"⏳ <b>Key hết hạn sau:</b> {expire} phút\n"
                    f"💡 <b>Lưu ý:</b> Không thoát khỏi trang Yeumoney trước khi click Tiếp tục"
                )
            else:
                text = (
                    f"⚠️ <b>Bot chưa rút gọn được link.</b>\n\n"
                    f"🔗 <b>Link gốc (bạn tự rút gọn qua Yeumoney):</b>\n"
                    f"<code>{html_module.escape(paste_url)}</code>\n\n"
                    f"📋 <b>Cách làm:</b>\n"
                    f"1. Vào yeumoney.com → rút gọn link bên trên\n"
                    f"2. Vượt link rút gọn → thấy KEY hiển thị\n"
                    f"3. Copy key → gửi bot: <code>/key [dán-key]</code>\n\n"
                    f"⏳ <b>Key hết hạn sau:</b> {expire} phút"
                )
        else:
            bot_username = context.bot.username or "bot"
            text = (
                f"❌ <b>Lỗi tạo link đích.</b>\n\n"
                f"🔑 <b>Key của bạn:</b> <code>{key}</code>\n\n"
                f"⚠️ Vui lòng tự rút gọn link này qua Yeumoney:\n"
                f"<code>https://t.me/{bot_username}?start={key}</code>\n\n"
                f"Sau khi vượt, nhấn Start để bot tự động nhận key."
            )

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    elif data == "balance":
        u = await get_user(user_id)
        model = u.get("selected_model") or DEFAULT_MODEL
        prices = await get_model_prices()
        price = 1
        for k, v in prices.items():
            if k.lower() in model.lower() or model.lower() in k.lower():
                price = v["price"]
                break
        await query.edit_message_text(
            f"💎 <b>Số dư tài khoản</b>\n\n"
            f"💰 <b>Req hiện có:</b> <code>{u.get('req_balance', 0)} req</code>\n"
            f"🔑 <b>Đã dùng:</b> {u.get('total_keys_used', 0)} key\n"
            f"📅 <b>Hôm nay:</b> {u.get('keys_today', 0)}/10 key\n"
            f"💬 <b>Tin nhắn:</b> {u.get('total_messages', 0)}\n"
            f"⚙️ <b>Model:</b> <code>{html_module.escape(model)}</code>\n"
            f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
            f"💰 <b>Giá chat:</b> {price} req/tin nhắn\n\n"
            f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>",
            parse_mode=ParseMode.HTML
        )

    elif data == "models":
        prices = await get_model_prices()
        buttons = []
        row = []
        for k, v in prices.items():
            if v["enabled"]:
                row.append(InlineKeyboardButton(f"{k[:15]} ({v['price']}r)", callback_data=f"sm|{k}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
        if row:
            buttons.append(row)
        await query.edit_message_text(
            "🤖 <b>Chọn Model AI</b>\n\n"
            "💡 <b>Gợi ý:</b>\n"
            "• Model <b>1 req</b> = Nhanh, phù hợp chat thường\n"
            "• Model <b>3-5 req</b> = Thông minh hơn, chuyên sâu\n\n"
            "Chọn model bên dưới:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "prompts":
        prompts = await get_all_prompts()
        buttons = []
        for name, content, enabled in prompts:
            if enabled:
                buttons.append([InlineKeyboardButton(name.upper(), callback_data=f"sp|{name}")])
        await query.edit_message_text(
            "🎭 <b>Chọn Tính Cách AI</b>\n\n"
            "• <b>DEFAULT</b> — Trợ lý cân bằng, đa năng\n"
            "• <b>CREATIVE</b> — Bay bổng, giàu cảm xúc\n"
            "• <b>CODER</b> — Lập trình viên chuyên nghiệp\n"
            "• <b>TEACHER</b> — Giáo viên kiên nhẫn\n\n"
            "Chọn tính cách bên dưới:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "support":
        await query.edit_message_text(
            f"📞 <b>Hỗ Trợ Denia AI</b>\n\n"
            f"📱 <b>Zalo / Telegram:</b> <code>{ADMIN_PHONE}</code>\n"
            f"⏰ <b>Giờ hỗ trợ:</b> 08:00 — 22:00 (GMT+7)\n\n"
            f"⚠️ Vui lòng không spam tin nhắn.\n"
            f"💬 Mô tả rõ vấn đề để được hỗ trợ nhanh nhất.",
            parse_mode=ParseMode.HTML
        )

    elif data == "top":
        top = await get_top_users()
        if not top:
            await query.edit_message_text("🏆 Chưa có dữ liệu xếp hạng.")
            return
        text = "🏆 <b>Bảng Xếp Hạng — Top 10</b>\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, u in enumerate(top):
            name = html_module.escape(u[1] or u[2] or f"User {u[0]}")
            text += f"{medals[i]} <b>{name}</b> — {u[3]} tin nhắn | {u[4]} req\n"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    elif data == "checkin":
        ok, bonus = await daily_checkin(user_id)
        if ok:
            await query.edit_message_text(
                f"📅 <b>Điểm danh thành công!</b>\n\n"
                f"🎉 Bạn nhận +{bonus} req miễn phí!\n"
                f"🌟 Hẹn gặp lại bạn vào ngày mai!",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                "⚠️ <b>Bạn đã điểm danh hôm nay rồi!</b>\n\n"
                "🌅 Hãy quay lại vào ngày mai để nhận thêm req nhé.",
                parse_mode=ParseMode.HTML
            )

    elif data.startswith("sm|"):
        model = data.split("|", 1)[1]
        await set_user_model(user_id, model)
        prices = await get_model_prices()
        price = prices.get(model, {}).get("price", 1)
        await query.edit_message_text(
            f"✅ <b>Đã chuyển model!</b>\n\n"
            f"⚙️ Model: <code>{html_module.escape(model)}</code>\n"
            f"💰 Giá: {price} req/tin nhắn\n\n"
            f"💬 Bắt đầu chat ngay bây giờ!",
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("sp|"):
        name = data.split("|", 1)[1]
        await set_user_prompt(user_id, name)
        await query.edit_message_text(
            f"🎭 <b>Đã chuyển tính cách!</b>\n\n"
            f"Tính cách: <b>{name.upper()}</b>\n"
            f"AI sẽ trả lời theo phong cách mới từ tin nhắn tiếp theo.",
            parse_mode=ParseMode.HTML
        )

# ========================
# CHAT HANDLER
# ========================
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_user(user_id)
    if u.get("banned"):
        return

    if await is_maintenance() and not is_admin(user_id):
        await update.message.reply_text(
            "🔧 <b>Bot đang bảo trì.</b>\n\n"
            "Vui lòng quay lại sau. Bạn vẫn có thể nhận key và điểm danh.",
            parse_mode=ParseMode.HTML
        )
        return

    ok, remain = await check_chat_cooldown(user_id)
    if not ok:
        await update.message.reply_text(f"⏳ Vui lòng đợi {remain} giây nữa.")
        return

    model = await get_user_model(user_id)
    prices = await get_model_prices()
    price = 1
    for k, v in prices.items():
        if k.lower() in model.lower() or model.lower() in k.lower():
            if v["enabled"]:
                price = v["price"]
            break

    success = await deduct_req(user_id, price)
    if not success:
        keyboard = [[InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")]]
        await update.message.reply_text(
            f"⚠️ <b>Bạn đã hết req!</b>\n\n"
            f"Cần {price} req để chat model này.\n"
            f"Nhấn nút bên dưới để nhận key.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return

    await update.message.chat.send_action(action="typing")
    try:
        reply, cost = await chat_ai(user_id, update.message.text)
        # Thêm thông tin số dư còn lại
        u_after = await get_user(user_id)
        remaining = u_after.get('req_balance', 0)
        if remaining <= price * 3:
            reply += f"\n\n💡 <b>Còn {remaining} req.</b> Gần hết req rồi, nhớ nhận key nhé!"
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
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
        f"📞 Admin: {ADMIN_PHONE}",
        parse_mode=ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    s = await get_stats()
    await update.message.reply_text(
        f"📊 <b>Thống Kê Denia AI</b>\n\n"
        f"👤 <b>Tổng users:</b> {s['total_users']}\n"
        f"💎 <b>Tổng req lưu hành:</b> {s['total_req']}\n"
        f"🔑 <b>Key đã dùng:</b> {s['total_keys']}\n"
        f"⏳ <b>Key chờ xử lý:</b> {s['pending_keys']}\n"
        f"💬 <b>Tin nhắn AI:</b> {s['total_messages']}\n"
        f"📅 <b>Hoạt động hôm nay:</b> {s['today_logs']}\n"
        f"📣 <b>Feedback chờ:</b> {s['pending_feedback']}\n\n"
        f"📞 Admin: {ADMIN_PHONE}",
        parse_mode=ParseMode.HTML
    )

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    logs = await get_recent_logs(50)
    text = "📋 <b>Logs Gần Đây (50):</b>\n\n"
    for l in logs:
        text += f"[{l[4][:16]}] <code>{l[0]}</code> | {html_module.escape(l[1] or 'N/A')} | <b>{l[2]}</b> | {html_module.escape(l[3])}\n"
    if len(text) > 4000:
        text = text[:4000] + "\n... (còn nhiều)"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    us = await get_users_list(20)
    text = "👤 <b>Danh Sách Users (20 gần nhất):</b>\n\n"
    for u in us:
        status = "🚫 BANNED" if u[6] else "✅ OK"
        name = html_module.escape(u[2] or u[1] or str(u[0]))
        text += f"<code>{u[0]}</code> | {name} | Req: {u[3]} | Keys: {u[4]} | Msg: {u[5]} | {status}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def user_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập user ID. Ví dụ: <code>/user 123456789</code>", parse_mode=ParseMode.HTML)
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")
        return
    u = await get_user(tid)
    logs = await get_user_logs(tid, 10)
    text = (
        f"👤 <b>Chi Tiết User {tid}</b>\n\n"
        f"Username: {html_module.escape(u.get('username') or 'N/A')}\n"
        f"Tên: {html_module.escape(u.get('first_name') or 'N/A')}\n"
        f"Req: {u.get('req_balance', 0)}\n"
        f"Keys used: {u.get('total_keys_used', 0)}\n"
        f"Messages: {u.get('total_messages', 0)}\n"
        f"Model: {html_module.escape(u.get('selected_model') or 'N/A')}\n"
        f"Prompt: {u.get('selected_prompt', 'default')}\n"
        f"Mã giới thiệu: <code>{u.get('referral_code', '')}</code>\n"
        f"Status: {'🚫 BANNED' if u.get('banned') else '✅ OK'}\n"
        f"Created: {u.get('created_at', 'N/A')}\n\n"
        f"<b>📋 Logs gần đây:</b>\n"
    )
    for l in logs:
        text += f"• {l[2]} | {l[0]} | {html_module.escape(l[1])}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def addreq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Ví dụ: <code>/addreq 123456789 100</code>", parse_mode=ParseMode.HTML)
        return
    try:
        tid = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Số không hợp lệ.")
        return
    await admin_add_req(tid, amount)
    await update.message.reply_text(f"✅ Đã nạp {amount} req cho user <code>{tid}</code>", parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(
            tid,
            f"💎 <b>Thông Báo Từ Admin</b>\n\n"
            f"Bạn vừa được cộng <b>{amount} req</b>!\n"
            f"Số dư hiện tại đã được cập nhật.",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/ban 123456789</code>", parse_mode=ParseMode.HTML)
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")
        return
    await admin_ban_user(tid, 1)
    await update.message.reply_text(f"🚫 Đã khóa user <code>{tid}</code>", parse_mode=ParseMode.HTML)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/unban 123456789</code>", parse_mode=ParseMode.HTML)
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")
        return
    await admin_ban_user(tid, 0)
    await update.message.reply_text(f"✅ Đã mở khóa user <code>{tid}</code>", parse_mode=ParseMode.HTML)

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cfg = await get_all_cfg()
    text = "⚙️ <b>Cấu Hình Hiện Tại:</b>\n\n"
    for k, v in cfg.items():
        text += f"• <code>{html_module.escape(k)}</code> = <code>{html_module.escape(v)}</code>\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def setconfig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Ví dụ: <code>/setconfig REQ_PER_LINK 300</code>\n"
            "Các key: REQ_PER_LINK, MAX_REQ_BALANCE, KEY_COOLDOWN_MINUTES, KEY_EXPIRE_MINUTES, MAX_KEYS_PER_DAY, "
            "CHAT_COOLDOWN_SECONDS, MAX_MEMORY_MESSAGES, DAILY_CHECKIN_REQ, REFERRAL_BONUS_REQ, MAINTENANCE_MODE, AUTO_CLEANUP_DAYS",
            parse_mode=ParseMode.HTML
        )
        return
    key = context.args[0].strip()
    value = " ".join(context.args[1:]).strip()
    await set_cfg(key, value)
    await update.message.reply_text(f"✅ Đã cập nhật: <code>{html_module.escape(key)}</code> = <code>{html_module.escape(value)}</code>", parse_mode=ParseMode.HTML)

async def setprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Ví dụ: <code>/setprice deepseek-v4-flash 2</code>", parse_mode=ParseMode.HTML)
        return
    model = context.args[0].strip()
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Giá phải là số.")
        return
    await set_model_price(model, price, 1)
    await update.message.reply_text(f"✅ Đã cập nhật giá: <code>{html_module.escape(model)}</code> = {price} req", parse_mode=ParseMode.HTML)

async def admin_models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    prices = await get_model_prices()
    text = "🤖 <b>Quản Lý Model:</b>\n\n"
    for k, v in prices.items():
        status = "✅ BẬT" if v["enabled"] else "❌ TẮT"
        text += f"• <code>{html_module.escape(k)}</code> | {v['price']} req | {status}\n"
    text += "\nDùng <code>/togglemodel [tên]</code> để bật/tắt."
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def togglemodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/togglemodel deepseek-v4-flash</code>", parse_mode=ParseMode.HTML)
        return
    model = " ".join(context.args).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT enabled FROM model_prices WHERE model_name = ?", (model,))
        row = await cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Model không tồn tại.")
            return
        new_state = 0 if row[0] else 1
        await db.execute("UPDATE model_prices SET enabled = ? WHERE model_name = ?", (new_state, model))
        await db.commit()
    await update.message.reply_text(f"✅ Model <code>{html_module.escape(model)}</code> đã {'BẬT' if new_state else 'TẮT'}", parse_mode=ParseMode.HTML)

async def admin_prompts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    prompts = await get_all_prompts()
    text = "🎭 <b>Quản Lý Prompt:</b>\n\n"
    for p in prompts:
        status = "✅ BẬT" if p[2] else "❌ TẮT"
        text += f"• <b>{p[0]}</b> | {status}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def addprompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Ví dụ: <code>/addprompt funny Bạn là hài hước...</code>", parse_mode=ParseMode.HTML)
        return
    name = context.args[0].strip().lower()
    content = " ".join(context.args[1:]).strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO prompts (name, content, enabled) VALUES (?, ?, 1)", (name, content))
        await db.commit()
    await update.message.reply_text(f"✅ Đã thêm prompt: <b>{name}</b>", parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/broadcast Chào tất cả! Có tin mới...</code>", parse_mode=ParseMode.HTML)
        return
    message = " ".join(context.args)
    users = await get_all_users()
    sent = 0
    failed = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 <b>Thông Báo Từ Admin:</b>\n\n{message}", parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.1)
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Đã gửi: {sent} users | ❌ Thất bại: {failed} users")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cfg = await get_all_cfg()
    current = cfg.get("MAINTENANCE_MODE", "0")
    new_val = "0" if current == "1" else "1"
    await set_cfg("MAINTENANCE_MODE", new_val)
    status = "BẬT" if new_val == "1" else "TẮT"
    await update.message.reply_text(f"🔧 Chế độ bảo trì đã {status}.", parse_mode=ParseMode.HTML)

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    status = []
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("SELECT 1")
        status.append("🟢 Database: OK")
    except Exception as e:
        status.append(f"🔴 Database: {e}")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(AI_BASE_URL.replace("/v1/chat/completions", "/v1/models"), headers={"Authorization": f"Bearer {AI_API_KEY}"})
            status.append("🟢 AI API: OK" if r.status_code in [200, 401, 403] else f"🟡 AI API: HTTP {r.status_code}")
    except Exception as e:
        status.append(f"🔴 AI API: {e}")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            import urllib.parse
            tu = f"{YEUMONEY_API_URL}?token={YEUMONEY_API_KEY}&url={urllib.parse.quote('https://google.com', safe='')}&format=json"
            r = await c.get(tu)
            status.append("🟢 Yeumoney: OK" if r.status_code == 200 else f"🟡 Yeumoney: HTTP {r.status_code}")
    except Exception as e:
        status.append(f"🔴 Yeumoney: {e}")
    await update.message.reply_text(f"🏥 <b>System Health Check</b>\n\n" + "\n".join(status), parse_mode=ParseMode.HTML)

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await auto_cleanup()
    await update.message.reply_text("🧹 Đã dọn dẹp dữ liệu cũ.", parse_mode=ParseMode.HTML)

async def feedback_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    fbs = await get_pending_feedback(20)
    if not fbs:
        await update.message.reply_text("✅ Không có feedback nào chờ xử lý.")
        return
    text = "📣 <b>Feedback Chờ Xử Lý:</b>\n\n"
    for f in fbs:
        text += f"#{f[0]} | User <code>{f[1]}</code> | {f[4][:16]}\n{html_module.escape(f[3][:200])}\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def feedback_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/feedbackdone 1</code>", parse_mode=ParseMode.HTML)
        return
    try:
        fid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")
        return
    await mark_feedback_done(fid)
    await update.message.reply_text(f"✅ Đã đánh dấu feedback #{fid} đã xử lý.")

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    import csv
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "username", "first_name", "req_balance", "total_keys", "total_messages", "banned", "created_at"])
    us = await get_users_list(10000)
    for u in us:
        writer.writerow([u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7]])
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode("utf-8-sig"),
        filename=f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        caption="📊 Xuất dữ liệu users thành công."
    )

async def error_handler(update, context):
    logger.error(f"Exception: {context.error}")
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML)
        except Exception:
            pass

async def post_init(app: Application):
    uc = [
        BotCommand("start", "Menu chính"), BotCommand("help", "Hướng dẫn"),
        BotCommand("key", "Nhập key nhận req"), BotCommand("model", "Chọn model AI"),
        BotCommand("prompt", "Chọn tính cách AI"), BotCommand("new", "Xóa lịch sử chat"),
        BotCommand("history", "Xem lịch sử"), BotCommand("profile", "Hồ sơ cá nhân"),
        BotCommand("balance", "Xem số dư"), BotCommand("top", "Bảng xếp hạng"),
        BotCommand("checkin", "Điểm danh nhận req"), BotCommand("ref", "Mã giới thiệu"),
        BotCommand("feedback", "Góp ý cho admin")
    ]
    ac = [
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
        BotCommand("export", "Xuất CSV")
    ]
    await app.bot.set_my_commands(uc, scope=BotCommandScopeDefault())
    if ADMIN_ID:
        try:
            await app.bot.set_my_commands(uc + ac, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        except Exception:
            pass
    logger.info("Commands set.")

def main():
    if not BOT_TOKEN or not AI_API_KEY:
        logger.error("Thiếu BOT_TOKEN hoặc AI_API_KEY!")
        sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("key", key_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("prompt", prompt_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("ref", ref_command))
    app.add_handler(CommandHandler("feedback", feedback_command))

    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("user", user_detail_command))
    app.add_handler(CommandHandler("addreq", addreq_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("setconfig", setconfig_command))
    app.add_handler(CommandHandler("setprice", setprice_command))
    app.add_handler(CommandHandler("models", admin_models_command))
    app.add_handler(CommandHandler("togglemodel", togglemodel_command))
    app.add_handler(CommandHandler("prompts", admin_prompts_command))
    app.add_handler(CommandHandler("addprompt", addprompt_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("maintenance", maintenance_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))
    app.add_handler(CommandHandler("feedbacklist", feedback_list_command))
    app.add_handler(CommandHandler("feedbackdone", feedback_done_command))
    app.add_handler(CommandHandler("export", export_command))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    app.add_error_handler(error_handler)

    logger.info("Denia Bot Ultimate starting...")
    asyncio.run(init_db())
    asyncio.run(init_model_prices())
    asyncio.run(auto_cleanup())
    logger.info(f"Ready. Admin: {ADMIN_PHONE} | Req/link: {REQ_PER_LINK}")
    if ADMIN_TELEGRAM_ID == 0:
        logger.info("Auto-admin enabled.")
    else:
        logger.info(f"Admin ID: {ADMIN_TELEGRAM_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
