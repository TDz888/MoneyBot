"""
🤖 DENIA AI BOT — ULTIMATE EDITION v3.0
Refactored: Stable | Professional | Zero-bug Logic
"""
import os, sys, random, string, logging, asyncio, html as html_module, csv, io, re
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
FLOOD_WINDOW_SECONDS = int(os.getenv("FLOOD_WINDOW_SECONDS", "60"))
FLOOD_MAX_MSG = int(os.getenv("FLOOD_MAX_MSG", "20"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek-v4-flash").strip()
MAX_MEMORY_MESSAGES = int(os.getenv("MAX_MEMORY_MESSAGES", "20"))
SYSTEM_PROMPT_DEFAULT = os.getenv("SYSTEM_PROMPT_DEFAULT", "Bạn là Denia AI, một trợ lý thông minh, thân thiện, hữu ích. Trả lời ngắn gọn, rõ ràng, dùng Markdown khi cần.").strip()
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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "denia_ultimate.db")
ADMIN_ID = ADMIN_TELEGRAM_ID

# ========================
# DATABASE
# ========================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = OFF")  # Avoid FK issues with admin keys
        await db.execute("PRAGMA journal_mode = WAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                req_balance INTEGER DEFAULT 0,
                req_spent INTEGER DEFAULT 0,
                req_earned INTEGER DEFAULT 0,
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                key_code TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                req_amount INTEGER DEFAULT 300,
                used INTEGER DEFAULT 0,
                used_by INTEGER,
                source TEXT DEFAULT 'user',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                note TEXT
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_keys_user ON keys(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_keys_used ON keys(used)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_keys_code ON keys(key_code)")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_chat_at TEXT,
                msg_count INTEGER DEFAULT 0,
                window_start TEXT
            )""")

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
                enabled INTEGER DEFAULT 1,
                description TEXT
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                name TEXT PRIMARY KEY,
                content TEXT,
                enabled INTEGER DEFAULT 1
            )""")

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
                admin_reply TEXT,
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

        # Defaults
        defaults = [
            ("REQ_PER_LINK", str(REQ_PER_LINK)),
            ("MAX_REQ_BALANCE", str(MAX_REQ_BALANCE)),
            ("KEY_COOLDOWN_MINUTES", str(KEY_COOLDOWN_MINUTES)),
            ("KEY_EXPIRE_MINUTES", str(KEY_EXPIRE_MINUTES)),
            ("MAX_KEYS_PER_DAY", str(MAX_KEYS_PER_DAY)),
            ("CHAT_COOLDOWN_SECONDS", str(CHAT_COOLDOWN_SECONDS)),
            ("FLOOD_WINDOW_SECONDS", str(FLOOD_WINDOW_SECONDS)),
            ("FLOOD_MAX_MSG", str(FLOOD_MAX_MSG)),
            ("DEFAULT_MODEL", DEFAULT_MODEL),
            ("MAX_MEMORY_MESSAGES", str(MAX_MEMORY_MESSAGES)),
            ("SYSTEM_PROMPT_DEFAULT", SYSTEM_PROMPT_DEFAULT),
            ("DAILY_CHECKIN_REQ", str(DAILY_CHECKIN_REQ)),
            ("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)),
            ("MAINTENANCE_MODE", str(MAINTENANCE_MODE)),
            ("AUTO_CLEANUP_DAYS", str(AUTO_CLEANUP_DAYS)),
        ]
        for k, v in defaults:
            await db.execute("INSERT OR IGNORE INTO runtime_config (key, value) VALUES (?, ?)", (k, v))

        prompts = [
            ("default", SYSTEM_PROMPT_DEFAULT),
            ("creative", "Bạn là Denia AI Creative — Nhà văn, nghệ sĩ sáng tạo. Trả lời bay bổng, giàu cảm xúc, dùng ẩn dụ, từ ngữ mỹ lệ."),
            ("coder", "Bạn là Denia AI Coder — Lập trình viên cao cấp. Trả lời bằng code, giải thích kỹ thuật chính xác, dùng markdown, nêu ví dụ rõ ràng."),
            ("teacher", "Bạn là Denia AI Teacher — Giáo viên kiên nhẫn. Giải thích từ cơ bản đến nâng cao, dùng ví dụ thực tế, khuyến khích người học."),
        ]
        for name, content in prompts:
            await db.execute("INSERT OR IGNORE INTO prompts (name, content) VALUES (?, ?)", (name, content))

        await db.commit()

async def init_model_prices():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM model_prices")
        if (await cur.fetchone())[0] == 0:
            for k, v in os.environ.items():
                if k.startswith("PRICE_"):
                    mn = k[6:].replace("_", "-").replace("--", "/")
                    await db.execute(
                        "INSERT INTO model_prices (model_name, req_price, enabled, description) VALUES (?, ?, ?, ?)",
                        (mn, int(v), 1, None)
                    )
            await db.commit()

async def init_app():
    await init_db()
    await init_model_prices()
    await auto_cleanup()

async def get_cfg(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM runtime_config WHERE key = ?", (key,))
        r = await cur.fetchone()
        return r[0] if r else default

async def set_cfg(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO runtime_config (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat())
        )
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
            now = datetime.now().isoformat()
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, selected_model, referral_code, last_active) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, DEFAULT_MODEL, ref, now)
            )
            await db.commit()
            return {
                "user_id": user_id, "username": username, "first_name": first_name,
                "req_balance": 0, "req_spent": 0, "req_earned": 0,
                "total_keys_used": 0, "total_messages": 0,
                "last_key_at": None, "keys_today": 0, "last_key_date": None,
                "selected_model": DEFAULT_MODEL, "selected_prompt": "default",
                "banned": 0, "referral_code": ref, "referred_by": None,
                "daily_checkin_date": None, "created_at": now, "last_active": now
            }
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

async def update_user_activity(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
            await db.commit()
    except Exception:
        pass

async def can_create_key(user_id: int) -> Tuple[bool, str]:
    cfg = await get_all_cfg()
    cooldown = int(cfg.get("KEY_COOLDOWN_MINUTES", KEY_COOLDOWN_MINUTES))
    max_day = int(cfg.get("MAX_KEYS_PER_DAY", MAX_KEYS_PER_DAY))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT last_key_at, keys_today, last_key_date, banned FROM users WHERE user_id = ?", (user_id,))
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

async def create_key(user_id: int, key_code: str, req_amount: int = None, source: str = "user", note: str = None) -> bool:
    cfg = await get_all_cfg()
    expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))
    if req_amount is None:
        req_amount = int(cfg.get("REQ_PER_LINK", REQ_PER_LINK))
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            exp = datetime.now() + timedelta(minutes=expire)
            await db.execute(
                "INSERT INTO keys (key_code, user_id, req_amount, expires_at, source, note) VALUES (?, ?, ?, ?, ?, ?)",
                (key_code.upper(), user_id, req_amount, exp.isoformat(), source, note)
            )
            if source == "user":
                today_str = datetime.now().strftime("%Y-%m-%d")
                await db.execute(
                    "UPDATE users SET last_key_at = ?, keys_today = keys_today + 1, last_key_date = ? WHERE user_id = ?",
                    (datetime.now().isoformat(), today_str, user_id)
                )
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"create_key error: {e}")
            return False

async def use_key(key_code: str, user_id: int) -> Dict[str, Any]:
    cfg = await get_all_cfg()
    max_bal = int(cfg.get("MAX_REQ_BALANCE", MAX_REQ_BALANCE))
    key_code = key_code.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, used, expires_at, req_amount, source, used_by FROM keys WHERE key_code = ?", (key_code,))
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "msg": "❌ Key không tồn tại trong hệ thống."}
        key_owner, used, expires_at, req_amount, source, used_by = row
        if used:
            return {"ok": False, "msg": "❌ Key đã được sử dụng trước đó."}
        if source == "user" and key_owner != user_id:
            return {"ok": False, "msg": "❌ Key này không thuộc về bạn. Mỗi key chỉ dùng cho người tạo ra nó."}
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.now():
                    await db.execute("UPDATE keys SET used = 1 WHERE key_code = ?", (key_code,))
                    await db.commit()
                    return {"ok": False, "msg": "⏳ Key đã hết hạn. Vui lòng nhận key mới."}
            except Exception:
                pass
        cur2 = await db.execute("SELECT req_balance, banned FROM users WHERE user_id = ?", (user_id,))
        row2 = await cur2.fetchone()
        if not row2 or row2[1]:
            return {"ok": False, "msg": "🚫 Tài khoản bị khóa hoặc không tồn tại."}
        bal = row2[0] or 0
        if bal + req_amount > max_bal:
            return {"ok": False, "msg": f"💎 Bạn đã đạt giới hạn tích lũy {max_bal} req. Hãy sử dụng bớt req trước khi nhận thêm."}
        await db.execute("UPDATE keys SET used = 1, used_by = ? WHERE key_code = ?", (user_id, key_code))
        await db.execute(
            "UPDATE users SET req_balance = req_balance + ?, req_earned = req_earned + ?, total_keys_used = total_keys_used + 1 WHERE user_id = ?",
            (req_amount, req_amount, user_id)
        )
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, "USE_KEY", f"{key_code} +{req_amount}req"))
        await db.commit()
        return {"ok": True, "msg": f"✅ Key hợp lệ! +{req_amount} req đã được cộng vào tài khoản."}

async def deduct_req(user_id: int, amount: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT req_balance, banned FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row or row[1] or (row[0] or 0) < amount:
            return False
        await db.execute(
            "UPDATE users SET req_balance = req_balance - ?, req_spent = req_spent + ?, total_messages = total_messages + 1 WHERE user_id = ?",
            (amount, amount, user_id)
        )
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, "CHAT", f"-{amount}req"))
        await db.commit()
        return True

async def check_chat_cooldown(user_id: int) -> Tuple[bool, int]:
    cfg = await get_all_cfg()
    cd = int(cfg.get("CHAT_COOLDOWN_SECONDS", CHAT_COOLDOWN_SECONDS))
    flood_win = int(cfg.get("FLOOD_WINDOW_SECONDS", FLOOD_WINDOW_SECONDS))
    flood_max = int(cfg.get("FLOOD_MAX_MSG", FLOOD_MAX_MSG))
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_chat_at, msg_count, window_start FROM cooldowns WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row and row[0]:
            try:
                last = datetime.fromisoformat(row[0])
                diff = (now - last).total_seconds()
                if diff < cd:
                    return False, int(cd - diff)
            except Exception:
                pass
        # Flood check
        if row and row[2]:
            try:
                win_start = datetime.fromisoformat(row[2])
                if (now - win_start).total_seconds() < flood_win:
                    if (row[1] or 0) >= flood_max:
                        return False, -1
                    await db.execute(
                        "INSERT OR REPLACE INTO cooldowns (user_id, last_chat_at, msg_count, window_start) VALUES (?, ?, ?, ?)",
                        (user_id, now.isoformat(), (row[1] or 0) + 1, row[2])
                    )
                else:
                    await db.execute(
                        "INSERT OR REPLACE INTO cooldowns (user_id, last_chat_at, msg_count, window_start) VALUES (?, ?, ?, ?)",
                        (user_id, now.isoformat(), 1, now.isoformat())
                    )
            except Exception:
                await db.execute(
                    "INSERT OR REPLACE INTO cooldowns (user_id, last_chat_at, msg_count, window_start) VALUES (?, ?, ?, ?)",
                    (user_id, now.isoformat(), 1, now.isoformat())
                )
        else:
            await db.execute(
                "INSERT OR REPLACE INTO cooldowns (user_id, last_chat_at, msg_count, window_start) VALUES (?, ?, ?, ?)",
                (user_id, now.isoformat(), 1, now.isoformat())
            )
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
        cur = await db.execute(
            "SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, 1000, mm)
        )
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
            (user_id, limit)
        )
        rows = await cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def clear_conversation(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_model_prices() -> Dict[str, Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT model_name, req_price, enabled, description FROM model_prices")
        rows = await cur.fetchall()
        return {r[0]: {"price": r[1], "enabled": r[2], "description": r[3]} for r in rows}

async def set_model_price(model_name: str, price: int, enabled: int = 1, description: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO model_prices (model_name, req_price, enabled, description) VALUES (?, ?, ?, ?)",
            (model_name, price, enabled, description)
        )
        await db.commit()

async def get_stats() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        tu = (await cur.fetchone())[0]
        cur = await db.execute("SELECT SUM(req_balance) FROM users")
        tr = (await cur.fetchone())[0] or 0
        cur = await db.execute("SELECT SUM(req_spent) FROM users")
        ts = (await cur.fetchone())[0] or 0
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
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
        tb = (await cur.fetchone())[0]
        return {
            "total_users": tu, "total_req": tr, "total_spent": ts,
            "total_keys": tk, "pending_keys": pk, "total_messages": tm,
            "today_logs": tl, "pending_feedback": pf, "banned_users": tb
        }

async def get_users_list(limit: int = 50, offset: int = 0) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, username, first_name, req_balance, req_spent, total_keys_used, total_messages, banned, created_at, selected_model, selected_prompt
            FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?""", (limit, offset))
        return await cur.fetchall()

async def get_top_users() -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id, first_name, username, total_messages, req_balance, req_spent
            FROM users ORDER BY total_messages DESC LIMIT 10""")
        return await cur.fetchall()

async def admin_add_req(user_id: int, amount: int, admin_id: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET req_balance = req_balance + ?, req_earned = req_earned + ? WHERE user_id = ?",
            (amount, amount, user_id)
        )
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, "ADMIN_ADD", f"Admin {admin_id} +{amount}req"))
        await db.commit()

async def admin_ban_user(user_id: int, ban: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned = ? WHERE user_id = ?", (ban, user_id))
        await db.commit()

async def get_user_logs(user_id: int, limit: int = 20) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT action, detail, created_at FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        return await cur.fetchall()

async def get_recent_logs(limit: int = 50, user_id: int = None) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id:
            cur = await db.execute("""
                SELECT l.user_id, u.username, l.action, l.detail, l.created_at
                FROM logs l LEFT JOIN users u ON l.user_id = u.user_id
                WHERE l.user_id = ? ORDER BY l.id DESC LIMIT ?""", (user_id, limit))
        else:
            cur = await db.execute("""
                SELECT l.user_id, u.username, l.action, l.detail, l.created_at
                FROM logs l LEFT JOIN users u ON l.user_id = u.user_id ORDER BY l.id DESC LIMIT ?""", (limit,))
        return await cur.fetchall()

async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE banned = 0")
        return [r[0] for r in await cur.fetchall()]

async def add_feedback(user_id: int, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO feedback (user_id, content) VALUES (?, ?)", (user_id, content))
        await db.commit()

async def get_pending_feedback(limit: int = 20) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT f.id, f.user_id, u.username, f.content, f.created_at, f.admin_reply
            FROM feedback f LEFT JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'pending' ORDER BY f.id DESC LIMIT ?""", (limit,))
        return await cur.fetchall()

async def mark_feedback_done(feedback_id: int, reply: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if reply:
            await db.execute(
                "UPDATE feedback SET status = 'done', admin_reply = ? WHERE id = ?",
                (reply, feedback_id)
            )
        else:
            await db.execute("UPDATE feedback SET status = 'done' WHERE id = ?", (feedback_id,))
        await db.commit()

async def check_referral(referrer_id: int, referred_id: int) -> bool:
    if referrer_id == referred_id:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,))
        if await cur.fetchone():
            return False
        bonus = int(await get_cfg("REFERRAL_BONUS_REQ", str(REFERRAL_BONUS_REQ)))
        await db.execute(
            "INSERT INTO referrals (referrer_id, referred_id, bonus_given) VALUES (?, ?, 1)",
            (referrer_id, referred_id)
        )
        await db.execute(
            "UPDATE users SET req_balance = req_balance + ?, req_earned = req_earned + ? WHERE user_id = ?",
            (bonus, bonus, referrer_id)
        )
        await db.execute(
            "UPDATE users SET req_balance = req_balance + ?, req_earned = req_earned + ? WHERE user_id = ?",
            (bonus, bonus, referred_id)
        )
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
        await db.execute(
            "UPDATE users SET daily_checkin_date = ?, req_balance = req_balance + ?, req_earned = req_earned + ? WHERE user_id = ?",
            (today, bonus, bonus, user_id)
        )
        await db.execute("INSERT INTO logs (user_id, action, detail) VALUES (?, ?, ?)",
            (user_id, "CHECKIN", f"+{bonus}req"))
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

async def get_user_keys(user_id: int, limit: int = 10) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT key_code, req_amount, used, created_at, expires_at, source FROM keys WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cur.fetchall()

async def revoke_key(key_code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT used FROM keys WHERE key_code = ?", (key_code.upper(),))
        row = await cur.fetchone()
        if not row or row[0] == 1:
            return False
        await db.execute("DELETE FROM keys WHERE key_code = ?", (key_code.upper(),))
        await db.commit()
        return True

async def get_pending_keys(limit: int = 20) -> List[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT key_code, req_amount, source, created_at, note FROM keys WHERE used = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return await cur.fetchall()

# ========================
# SERVICES
# ========================
def generate_key() -> str:
    p1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    p2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=2))
    p3 = "".join(random.choices(string.ascii_uppercase + string.digits, k=13))
    p4 = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"DENIA-{p1}-{p2}-{p3}-{p4}"

async def create_paste_dpaste(key: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            content_text = f"Mã kích hoạt Denia AI\n\n{key}\n\nCopy mã trên và gửi lại bot: /key {key}"
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
# FORMATTING HELPERS
# ========================
def esc(text) -> str:
    return html_module.escape(str(text) if text is not None else "")

def back_btn(data: str = "menu") -> List[List[InlineKeyboardButton]]:
    return [[InlineKeyboardButton("🔙 Quay lại", callback_data=data)]]

# ========================
# MENU BUILDER (shared)
# ========================
async def build_main_menu(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    u = await get_user(user_id)
    prices = await get_model_prices()
    price_list = "\n".join([
        f"• <code>{esc(k)}</code>: {v['price']} req"
        for k, v in prices.items() if v["enabled"]
    ]) or "• Chưa có model nào được cấu hình."

    text = (
        f"👋 <b>Xin chào {esc(u.get('first_name') or 'bạn')}!</b>\n\n"
        f"🤖 <b>Denia AI Bot</b> — Trợ lý AI thông minh, có trí nhớ!\n\n"
        f"💎 <b>Số dư:</b> <code>{u.get('req_balance', 0)} req</code>\n"
        f"⚙️ <b>Model:</b> <code>{esc(u.get('selected_model') or DEFAULT_MODEL)}</code>\n"
        f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
        f"💰 <b>Giá chat:</b> <code>{get_model_price(u.get('selected_model') or DEFAULT_MODEL)} req</code>/tin nhắn\n\n"
        f"<b>📋 Bảng giá model:</b>\n{price_list}\n\n"
        f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>\n"
        f"💡 Gõ /help để xem hướng dẫn chi tiết."
    )
    keyboard = [
        [InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")],
        [InlineKeyboardButton("📅 Điểm Danh", callback_data="checkin"), InlineKeyboardButton("💎 Số Dư", callback_data="balance")],
        [InlineKeyboardButton("🤖 Chọn Model", callback_data="models"), InlineKeyboardButton("🎭 Tính Cách", callback_data="prompts")],
        [InlineKeyboardButton("🏆 Bảng Xếp Hạng", callback_data="top"), InlineKeyboardButton("📞 Hỗ Trợ", callback_data="support")],
    ]
    return text, InlineKeyboardMarkup(keyboard)

# ========================
# USER HANDLERS
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        args = context.args
        await update_user_activity(user.id)

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
                        f"🎉 <b>Chào mừng trở lại!</b>\n\n{result['msg']}\n\n"
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
                                f"🎉 <b>Chào mừng!</b> Bạn được mời bởi user <code>{row[0]}</code>.\n"
                                f"💎 Cả 2 bạn đều nhận +{bonus} req!",
                                parse_mode=ParseMode.HTML
                            )
                            try:
                                await context.bot.send_message(
                                    row[0],
                                    f"🎉 <b>Chúc mừng!</b> User <code>{user.id}</code> đã dùng mã giới thiệu của bạn.\n"
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

        text, markup = await build_main_menu(user.id)
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"start error: {e}")
        await update.message.reply_text("❌ Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "📖 <b>Hướng Dẫn Sử Dụng — Denia AI</b>\n\n"
            "<b>🎯 Cách nhận req (3 bước đơn giản):</b>\n"
            "1️⃣ Nhấn <b>🔑 Nhận Key Mới</b> trên menu\n"
            "2️⃣ Bot tạo link rút gọn qua Yeumoney\n"
            "3️⃣ <b>Copy link</b> → mở trình duyệt → vượt → thấy <b>KEY</b> hiện ra\n"
            "4️⃣ Copy KEY → gửi bot: <code>/key DENIA-XXXXXX-XX-XXXXXXXXXXXXX-XXX</code>\n"
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
            "• <code>/feedback</code> — Góp ý cho admin\n"
            "• <code>/mykeys</code> — Lịch sử key\n\n"
            "<b>⚠️ Lưu ý:</b>\n"
            "• Mỗi tin nhắn AI tốn req tùy model (1-5 req)\n"
            "• Nhận key cách nhau 15 phút, tối đa 10/ngày\n"
            "• Giới hạn tích lũy: 5000 req\n"
            "• Key hết hạn sau 120 phút nếu không dùng\n\n"
            f"📞 <b>Hỗ trợ:</b> <code>{esc(ADMIN_PHONE)}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"help error: {e}")

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text(
                "⚠️ Vui lòng gửi kèm mã key.\n"
                "Ví dụ: <code>/key DENIA-A1B2C3-D4-E5F6G7H8I9J10-K11</code>",
                parse_mode=ParseMode.HTML
            )
            return
        key_input = context.args[0].strip().upper()
        if not key_input.startswith("DENIA-"):
            await update.message.reply_text("❌ Key phải bắt đầu bằng <code>DENIA-</code>", parse_mode=ParseMode.HTML)
            return
        result = await use_key(key_input, user_id)
        await update.message.reply_text(result["msg"], parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"key_command error: {e}")
        await update.message.reply_text("❌ Lỗi xử lý key. Vui lòng thử lại.", parse_mode=ParseMode.HTML)

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        prices = await get_model_prices()
        if not context.args:
            current = await get_user_model(user_id)
            buttons = []
            row = []
            for k, v in prices.items():
                if v["enabled"]:
                    label = f"{k[:15]} ({v['price']}r)"
                    row.append(InlineKeyboardButton(label, callback_data=f"sm|{k}"))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
            if row:
                buttons.append(row)
            buttons.append(back_btn("menu"))
            await update.message.reply_text(
                f"⚙️ <b>Model hiện tại:</b> <code>{esc(current)}</code>\n\nChọn model bên dưới:",
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
            f"✅ Đã chuyển sang model: <code>{esc(model_name)}</code>\n"
            f"💰 Giá: {prices[model_name]['price']} req/tin nhắn",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"model_command error: {e}")

async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        prompts = await get_all_prompts()
        if not context.args:
            current = await get_user_prompt(user_id)
            buttons = []
            for name, content, enabled in prompts:
                if enabled:
                    buttons.append([InlineKeyboardButton(name.upper(), callback_data=f"sp|{name}")])
            buttons.append(back_btn("menu"))
            await update.message.reply_text(
                f"🎭 <b>Tính cách hiện tại:</b> <code>{current}</code>\n\nChọn tính cách bên dưới:",
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
    except Exception as e:
        logger.error(f"prompt_command error: {e}")

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        keyboard = [
            [InlineKeyboardButton("✅ Xác nhận xóa", callback_data="confirm_new")],
            [InlineKeyboardButton("❌ Hủy", callback_data="cancel_new")]
        ]
        await update.message.reply_text(
            "🧠 <b>Xóa lịch sử chat?</b>\n\n"
            "AI sẽ không còn nhớ gì về cuộc trò chuyện trước.\n"
            "Bạn có chắc chắn muốn xóa?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"new_command error: {e}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        hist = await get_conversation_history(user_id, limit=10)
        if not hist:
            await update.message.reply_text("📝 Chưa có lịch sử chat nào.")
            return
        text = "📝 <b>Lịch sử chat gần đây:</b>\n\n"
        for msg in hist:
            role = "👤 Bạn" if msg["role"] == "user" else "🤖 AI"
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            text += f"{role}: {esc(content)}\n\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"history_command error: {e}")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        u = await get_user(user_id)
        model = u.get("selected_model") or DEFAULT_MODEL
        prices = await get_model_prices()
        price = 1
        for k, v in prices.items():
            if k.lower() in model.lower() or model.lower() in k.lower():
                price = v["price"]
                break
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
            ref_count = (await cur.fetchone())[0] or 0
        await update.message.reply_text(
            f"👤 <b>Hồ sơ của bạn</b>\n\n"
            f"🆔 <b>ID:</b> <code>{u['user_id']}</code>\n"
            f"👤 <b>Tên:</b> {esc(u.get('first_name') or 'N/A')}\n"
            f"💎 <b>Số dư:</b> <code>{u.get('req_balance', 0)} req</code>\n"
            f"📥 <b>Đã nhận:</b> <code>{u.get('req_earned', 0)} req</code>\n"
            f"📤 <b>Đã dùng:</b> <code>{u.get('req_spent', 0)} req</code>\n"
            f"🔑 <b>Đã dùng:</b> {u.get('total_keys_used', 0)} key\n"
            f"💬 <b>Tin nhắn:</b> {u.get('total_messages', 0)}\n"
            f"📅 <b>Tham gia:</b> {u.get('created_at', 'N/A')[:10]}\n"
            f"⚙️ <b>Model:</b> <code>{esc(model)}</code>\n"
            f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
            f"💰 <b>Giá chat:</b> {price} req/tin nhắn\n"
            f"👥 <b>Đã mời:</b> {ref_count} người\n"
            f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>\n",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"profile_command error: {e}")

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        top = await get_top_users()
        if not top:
            await update.message.reply_text("🏆 Chưa có dữ liệu xếp hạng.")
            return
        text = "🏆 <b>Bảng Xếp Hạng — Top 10</b>\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, u in enumerate(top):
            name = esc(u[1] or u[2] or f"User {u[0]}")
            text += f"{medals[i]} <b>{name}</b> — {u[3]} tin nhắn | 💎{u[4]} | 📤{u[5]}\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"top_command error: {e}")

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logger.error(f"checkin_command error: {e}")

async def ref_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logger.error(f"ref_command error: {e}")

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            "✅ <b>Cảm ơn bạn đã góp ý!</b>\n\nAdmin sẽ xem xét và phản hồi sớm nhất.",
            parse_mode=ParseMode.HTML
        )
        try:
            if ADMIN_ID and ADMIN_ID != 0:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"📣 <b>Feedback mới từ</b> <code>{user_id}</code>:\n{esc(content[:500])}",
                    parse_mode=ParseMode.HTML
                )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"feedback_command error: {e}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        u = await get_user(user_id)
        model = u.get("selected_model") or DEFAULT_MODEL
        prices = await get_model_prices()
        price = 1
        for k, v in prices.items():
            if k.lower() in model.lower() or model.lower() in k.lower():
                price = v["price"]
                break
        keyboard = [
            [InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")],
            [InlineKeyboardButton("📅 Điểm Danh", callback_data="checkin")],
            back_btn("menu")
        ]
        await update.message.reply_text(
            f"💎 <b>Số dư tài khoản</b>\n\n"
            f"💰 <b>Req hiện có:</b> <code>{u.get('req_balance', 0)} req</code>\n"
            f"📥 <b>Đã nhận:</b> <code>{u.get('req_earned', 0)} req</code>\n"
            f"📤 <b>Đã dùng:</b> <code>{u.get('req_spent', 0)} req</code>\n"
            f"🔑 <b>Key đã dùng:</b> {u.get('total_keys_used', 0)}\n"
            f"📅 <b>Hôm nay:</b> {u.get('keys_today', 0)}/10 key\n"
            f"💬 <b>Tin nhắn:</b> {u.get('total_messages', 0)}\n"
            f"⚙️ <b>Model:</b> <code>{esc(model)}</code>\n"
            f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
            f"💰 <b>Giá chat:</b> {price} req/tin nhắn\n\n"
            f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"balance_command error: {e}")

async def mykeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        keys = await get_user_keys(user_id, limit=10)
        if not keys:
            await update.message.reply_text("🔑 Bạn chưa có key nào.")
            return
        text = "🔑 <b>Lịch sử key gần đây:</b>\n\n"
        for k in keys:
            status = "✅ Đã dùng" if k[2] else "⏳ Chưa dùng"
            if k[4] and not k[2]:
                try:
                    if datetime.fromisoformat(k[4]) < datetime.now():
                        status = "❌ Đã hết hạn"
                except Exception:
                    pass
            text += f"<code>{esc(k[0])}</code> | {k[1]} req | {status}\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"mykeys_command error: {e}")

# ========================
# CALLBACK HANDLER (USER)
# ========================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    user_id = query.from_user.id
    data = query.data

    try:
        if data == "menu":
            text, markup = await build_main_menu(user_id)
            await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
            return

        if data == "getkey":
            ok, msg = await can_create_key(user_id)
            if not ok:
                await query.edit_message_text(f"⚠️ {msg}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("menu")))
                return

            key = generate_key()
            cfg = await get_all_cfg()
            req_per = int(cfg.get("REQ_PER_LINK", REQ_PER_LINK))
            if not await create_key(user_id, key, req_amount=req_per, source="user"):
                await query.edit_message_text("❌ Lỗi hệ thống khi tạo key. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("menu")))
                return

            paste_url = await create_paste_dpaste(key)
            expire = int(cfg.get("KEY_EXPIRE_MINUTES", KEY_EXPIRE_MINUTES))

            if paste_url:
                short_link = await shorten_yeumoney(paste_url)
                if short_link:
                    text = (
                        f"🔐 <b>Link vượt của bạn đã sẵn sàng!</b>\n\n"
                        f"🔗 <b>Link rút gọn Yeumoney:</b>\n"
                        f"<code>{esc(short_link)}</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📋 <b>Hướng dẫn vượt link (3 bước):</b>\n\n"
                        f"1️⃣ <b>Copy link</b> bên trên → mở <b>trình duyệt</b> (Chrome/Safari)\n"
                        f"2️⃣ Vượt Yeumoney (chờ 15-30 giây) → Click <b>Tiếp tục</b>\n"
                        f"3️⃣ Bạn sẽ thấy <b>KEY</b> hiển thị trên trang → <b>Copy key</b>\n\n"
                        f"✏️ <b>Sau khi có key, gửi lại bot:</b>\n"
                        f"<code>/key [dán-key-vừa-copy]</code>\n\n"
                        f"💎 Bot sẽ cộng <b>{req_per} req</b> ngay lập tức!\n\n"
                        f"⏳ <b>Key hết hạn sau:</b> {expire} phút\n"
                        f"💡 <b>Lưu ý:</b> Không thoát khỏi trang Yeumoney trước khi click Tiếp tục"
                    )
                else:
                    text = (
                        f"⚠️ <b>Bot chưa rút gọn được link.</b>\n\n"
                        f"🔗 <b>Link gốc (bạn tự rút gọn qua Yeumoney):</b>\n"
                        f"<code>{esc(paste_url)}</code>\n\n"
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
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("menu")), disable_web_page_preview=True)

        elif data == "balance":
            u = await get_user(user_id)
            model = u.get("selected_model") or DEFAULT_MODEL
            prices = await get_model_prices()
            price = 1
            for k, v in prices.items():
                if k.lower() in model.lower() or model.lower() in k.lower():
                    price = v["price"]
                    break
            text = (
                f"💎 <b>Số dư tài khoản</b>\n\n"
                f"💰 <b>Req hiện có:</b> <code>{u.get('req_balance', 0)} req</code>\n"
                f"📥 <b>Đã nhận:</b> <code>{u.get('req_earned', 0)} req</code>\n"
                f"📤 <b>Đã dùng:</b> <code>{u.get('req_spent', 0)} req</code>\n"
                f"🔑 <b>Đã dùng:</b> {u.get('total_keys_used', 0)} key\n"
                f"📅 <b>Hôm nay:</b> {u.get('keys_today', 0)}/10 key\n"
                f"💬 <b>Tin nhắn:</b> {u.get('total_messages', 0)}\n"
                f"⚙️ <b>Model:</b> <code>{esc(model)}</code>\n"
                f"🎭 <b>Tính cách:</b> <code>{u.get('selected_prompt', 'default')}</code>\n"
                f"💰 <b>Giá chat:</b> {price} req/tin nhắn\n\n"
                f"🎁 <b>Mã giới thiệu:</b> <code>{u.get('referral_code', '')}</code>"
            )
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("menu")))

        elif data == "models":
            prices = await get_model_prices()
            buttons = []
            row = []
            for k, v in prices.items():
                if v["enabled"]:
                    label = f"{k[:15]} ({v['price']}r)"
                    row.append(InlineKeyboardButton(label, callback_data=f"sm|{k}"))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
            if row:
                buttons.append(row)
            buttons.append(back_btn("menu"))
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
            buttons.append(back_btn("menu"))
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
                f"📱 <b>Zalo / Telegram:</b> <code>{esc(ADMIN_PHONE)}</code>\n"
                f"⏰ <b>Giờ hỗ trợ:</b> 08:00 — 22:00 (GMT+7)\n\n"
                f"⚠️ Vui lòng không spam tin nhắn.\n"
                f"💬 Mô tả rõ vấn đề để được hỗ trợ nhanh nhất.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("menu"))
            )

        elif data == "top":
            top = await get_top_users()
            if not top:
                await query.edit_message_text("🏆 Chưa có dữ liệu xếp hạng.", reply_markup=InlineKeyboardMarkup(back_btn("menu")))
                return
            text = "🏆 <b>Bảng Xếp Hạng — Top 10</b>\n\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i, u in enumerate(top):
                name = esc(u[1] or u[2] or f"User {u[0]}")
                text += f"{medals[i]} <b>{name}</b> — {u[3]} tin nhắn | 💎{u[4]} | 📤{u[5]}\n"
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("menu")))

        elif data == "checkin":
            ok, bonus = await daily_checkin(user_id)
            if ok:
                await query.edit_message_text(
                    f"📅 <b>Điểm danh thành công!</b>\n\n"
                    f"🎉 Bạn nhận +{bonus} req miễn phí!\n"
                    f"🌟 Hẹn gặp lại bạn vào ngày mai!",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back_btn("menu"))
                )
            else:
                await query.edit_message_text(
                    "⚠️ <b>Bạn đã điểm danh hôm nay rồi!</b>\n\n"
                    "🌅 Hãy quay lại vào ngày mai để nhận thêm req nhé.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back_btn("menu"))
                )

        elif data.startswith("sm|"):
            model = data.split("|", 1)[1]
            await set_user_model(user_id, model)
            prices = await get_model_prices()
            price = prices.get(model, {}).get("price", 1)
            await query.edit_message_text(
                f"✅ <b>Đã chuyển model!</b>\n\n"
                f"⚙️ Model: <code>{esc(model)}</code>\n"
                f"💰 Giá: {price} req/tin nhắn\n\n"
                f"💬 Bắt đầu chat ngay bây giờ!",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("menu"))
            )

        elif data.startswith("sp|"):
            name = data.split("|", 1)[1]
            await set_user_prompt(user_id, name)
            await query.edit_message_text(
                f"🎭 <b>Đã chuyển tính cách!</b>\n\n"
                f"Tính cách: <b>{name.upper()}</b>\n"
                f"AI sẽ trả lời theo phong cách mới từ tin nhắn tiếp theo.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("menu"))
            )

        elif data == "confirm_new":
            await clear_conversation(user_id)
            await query.edit_message_text(
                "🧠 <b>Đã xóa lịch sử chat!</b>\n\n"
                "AI không còn nhớ gì về cuộc trò chuyện trước.\n"
                "Bạn có thể bắt đầu chủ đề mới ngay bây giờ.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("menu"))
            )

        elif data == "cancel_new":
            await query.edit_message_text(
                "✅ <b>Đã hủy.</b> Lịch sử chat vẫn được giữ nguyên.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("menu"))
            )

    except Exception as e:
        logger.error(f"button_callback error: {e}")
        try:
            await query.edit_message_text("❌ Đã xảy ra lỗi. Vui lòng thử lại.", parse_mode=ParseMode.HTML)
        except Exception:
            pass

# ========================
# CHAT HANDLER
# ========================
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        await update_user_activity(user_id)
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
            if remain == -1:
                await update.message.reply_text(
                    "🛑 <b>Phát hiện spam!</b>\n"
                    "Bạn gửi tin nhắn quá nhanh. Vui lòng chậm lại.",
                    parse_mode=ParseMode.HTML
                )
            else:
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
            keyboard = [
                [InlineKeyboardButton("🔑 Nhận Key Mới", callback_data="getkey")],
                [InlineKeyboardButton("📅 Điểm Danh", callback_data="checkin")]
            ]
            await update.message.reply_text(
                f"⚠️ <b>Bạn đã hết req!</b>\n\n"
                f"Cần {price} req để chat model này.\n"
                f"Nhấn nút bên dưới để nhận key hoặc điểm danh.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            return

        await update.message.chat.send_action(action="typing")
        reply, cost = await chat_ai(user_id, update.message.text)
        u_after = await get_user(user_id)
        remaining = u_after.get('req_balance', 0)
        if remaining <= price * 3:
            reply += f"\n\n💡 <b>Còn {remaining} req.</b> Gần hết req rồi, nhớ nhận key nhé!"
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        await update.message.reply_text("❌ AI đang bận. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML)

# ========================
# ADMIN HANDLERS
# ========================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        await auto_set_admin(user_id)
        if not is_admin(user_id):
            await update.message.reply_text("❌ Bạn không có quyền admin.")
            return

        keyboard = [
            [InlineKeyboardButton("📊 Thống kê", callback_data="adm_stats"), InlineKeyboardButton("👤 Users", callback_data="adm_users")],
            [InlineKeyboardButton("🔑 Keys", callback_data="adm_keys"), InlineKeyboardButton("⚙️ Config", callback_data="adm_config")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"), InlineKeyboardButton("🏥 Health", callback_data="adm_health")],
            [InlineKeyboardButton("🧹 Cleanup", callback_data="adm_cleanup"), InlineKeyboardButton("📥 Export", callback_data="adm_export")],
        ]
        await update.message.reply_text(
            "🔐 <b>ADMIN PANEL — Denia AI</b>\n\n"
            "<b>📊 Thống kê:</b> /stats\n"
            "<b>👤 Users:</b> /users, /user [id]\n"
            "<b>💎 Nạp req:</b> /addreq [id] [số]\n"
            "<b>🎁 Tặng req:</b> /gift [id] [số]\n"
            "<b>🔑 Tạo key:</b> /genkey [req]\n"
            "<b>🗑️ Thu hồi:</b> /revoke [key]\n"
            "<b>🚫 Ban:</b> /ban [id], /unban [id]\n"
            "<b>⚙️ Config:</b> /config, /setconfig [key] [value]\n"
            "<b>📢 Broadcast:</b> /broadcast [tin nhắn]\n"
            "<b>🧹 Cleanup:</b> /cleanup\n"
            "<b>📥 Export:</b> /export\n"
            "<b>🏥 Health:</b> /health\n\n"
            f"📞 Admin: {esc(ADMIN_PHONE)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"admin_command error: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        s = await get_stats()
        await update.message.reply_text(
            f"📊 <b>Thống Kê Denia AI</b>\n\n"
            f"👤 <b>Tổng users:</b> {s['total_users']}\n"
            f"💎 <b>Tổng req lưu hành:</b> {s['total_req']}\n"
            f"📤 <b>Tổng req đã dùng:</b> {s['total_spent']}\n"
            f"🔑 <b>Key đã dùng:</b> {s['total_keys']}\n"
            f"⏳ <b>Key chờ xử lý:</b> {s['pending_keys']}\n"
            f"💬 <b>Tin nhắn AI:</b> {s['total_messages']}\n"
            f"📅 <b>Hoạt động hôm nay:</b> {s['today_logs']}\n"
            f"📣 <b>Feedback chờ:</b> {s['pending_feedback']}\n"
            f"🚫 <b>Users bị khóa:</b> {s['banned_users']}\n\n"
            f"📞 Admin: {esc(ADMIN_PHONE)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"stats_command error: {e}")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        target = None
        if context.args:
            try:
                target = int(context.args[0])
            except ValueError:
                pass
        logs = await get_recent_logs(50, user_id=target)
        text = f"📋 <b>Logs Gần Đây (50){' — User ' + str(target) if target else ''}:</b>\n\n"
        for l in logs:
            text += f"[{esc(l[4][:16])}] <code>{l[0]}</code> | {esc(l[1] or 'N/A')} | <b>{l[2]}</b> | {esc(l[3])}\n"
        if len(text) > 4000:
            text = text[:4000] + "\n... (còn nhiều)"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"logs_command error: {e}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        us = await get_users_list(20)
        text = "👤 <b>Danh Sách Users (20 gần nhất):</b>\n\n"
        for u in us:
            status = "🚫 BANNED" if u[7] else "✅ OK"
            name = esc(u[2] or u[1] or str(u[0]))
            text += f"<code>{u[0]}</code> | {name} | 💎{u[3]} | 📤{u[4]} | 🔑{u[5]} | 💬{u[6]} | {status}\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"users_command error: {e}")

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
    try:
        u = await get_user(tid)
        logs = await get_user_logs(tid, 10)
        keys = await get_user_keys(tid, 5)
        text = (
            f"👤 <b>Chi Tiết User {tid}</b>\n\n"
            f"Username: {esc(u.get('username') or 'N/A')}\n"
            f"Tên: {esc(u.get('first_name') or 'N/A')}\n"
            f"💎 Req: {u.get('req_balance', 0)} (Nhận: {u.get('req_earned', 0)}, Dùng: {u.get('req_spent', 0)})\n"
            f"🔑 Keys used: {u.get('total_keys_used', 0)}\n"
            f"💬 Messages: {u.get('total_messages', 0)}\n"
            f"⚙️ Model: {esc(u.get('selected_model') or 'N/A')}\n"
            f"🎭 Prompt: {u.get('selected_prompt', 'default')}\n"
            f"🎁 Mã giới thiệu: <code>{u.get('referral_code', '')}</code>\n"
            f"Status: {'🚫 BANNED' if u.get('banned') else '✅ OK'}\n"
            f"Created: {u.get('created_at', 'N/A')}\n"
            f"Last Active: {u.get('last_active', 'N/A')}\n\n"
            f"<b>🔑 Key gần đây:</b>\n"
        )
        for k in keys:
            text += f"<code>{esc(k[0])}</code> | {k[1]} req | {'✅' if k[2] else '⏳'}\n"
        text += f"\n<b>📋 Logs gần đây:</b>\n"
        for l in logs:
            text += f"• {l[2]} | {l[0]} | {esc(l[1])}\n"

        keyboard = [
            [InlineKeyboardButton("💎 +100 req", callback_data=f"adm_addreq|{tid}|100"), InlineKeyboardButton("💎 +500 req", callback_data=f"adm_addreq|{tid}|500")],
            [InlineKeyboardButton("🚫 Ban", callback_data=f"adm_ban|{tid}"), InlineKeyboardButton("✅ Unban", callback_data=f"adm_unban|{tid}")],
            [InlineKeyboardButton("📋 Xem logs", callback_data=f"adm_logs|{tid}")]
        ]
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"user_detail_command error: {e}")

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
    try:
        await admin_add_req(tid, amount, update.effective_user.id)
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
    except Exception as e:
        logger.error(f"addreq_command error: {e}")

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Ví dụ: <code>/gift 123456789 500</code>", parse_mode=ParseMode.HTML)
        return
    try:
        tid = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Số không hợp lệ.")
        return
    try:
        await admin_add_req(tid, amount, update.effective_user.id)
        await update.message.reply_text(
            f"🎁 <b>Đã tặng {amount} req</b> cho user <code>{tid}</code>\n"
            f"Lý do: Admin tặng",
            parse_mode=ParseMode.HTML
        )
        try:
            await context.bot.send_message(
                tid,
                f"🎁 <b>Quà tặng từ Admin!</b>\n\n"
                f"Bạn vừa nhận được <b>{amount} req</b> từ admin.\n"
                f"Hãy tiếp tục trải nghiệm Denia AI nhé!",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"gift_command error: {e}")

async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        req_amount = int(context.args[0]) if context.args else 100
    except ValueError:
        req_amount = 100
    try:
        admin_id = update.effective_user.id
        key = generate_key()
        if await create_key(admin_id, key, req_amount=req_amount, source="admin", note=f"Created by admin {admin_id}"):
            await update.message.reply_text(
                f"🔑 <b>Key trực tiếp đã tạo!</b>\n\n"
                f"<code>{key}</code>\n\n"
                f"💎 Giá trị: <b>{req_amount} req</b>\n"
                f"📤 Gửi key này cho user, họ dùng <code>/key {key}</code> để nhận.\n"
                f"⚠️ Key này dùng được cho <b>bất kỳ ai</b> (1 lần).",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ Lỗi tạo key.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"genkey_command error: {e}")
        await update.message.reply_text("❌ Lỗi tạo key.", parse_mode=ParseMode.HTML)

async def admin_keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        keys = await get_pending_keys(20)
        if not keys:
            await update.message.reply_text("✅ Không có key nào đang chờ.")
            return
        text = "🔑 <b>Key chưa sử dụng (20 gần nhất):</b>\n\n"
        for r in keys:
            src = "🤖 User" if r[2] == "user" else "👤 Admin"
            text += f"<code>{esc(r[0])}</code> | {r[1]} req | {src} | {r[3][:16]}\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"admin_keys_command error: {e}")

async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/revoke DENIA-XXXXXX-XX-XXXXXXXXXXXXX-XXX</code>", parse_mode=ParseMode.HTML)
        return
    try:
        key = context.args[0].strip().upper()
        if await revoke_key(key):
            await update.message.reply_text(f"✅ Đã thu hồi key <code>{key}</code>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Key không tồn tại hoặc đã được sử dụng.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"revoke_command error: {e}")

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
    try:
        await admin_ban_user(tid, 1)
        await update.message.reply_text(f"🚫 Đã khóa user <code>{tid}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"ban_command error: {e}")

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
    try:
        await admin_ban_user(tid, 0)
        await update.message.reply_text(f"✅ Đã mở khóa user <code>{tid}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"unban_command error: {e}")

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        cfg = await get_all_cfg()
        text = "⚙️ <b>Cấu Hình Hiện Tại:</b>\n\n"
        for k, v in cfg.items():
            text += f"• <code>{esc(k)}</code> = <code>{esc(v)}</code>\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"config_command error: {e}")

async def setconfig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Ví dụ: <code>/setconfig REQ_PER_LINK 300</code>\n"
            "Các key: REQ_PER_LINK, MAX_REQ_BALANCE, KEY_COOLDOWN_MINUTES, KEY_EXPIRE_MINUTES, MAX_KEYS_PER_DAY, "
            "CHAT_COOLDOWN_SECONDS, FLOOD_WINDOW_SECONDS, FLOOD_MAX_MSG, DEFAULT_MODEL, MAX_MEMORY_MESSAGES, "
            "DAILY_CHECKIN_REQ, REFERRAL_BONUS_REQ, MAINTENANCE_MODE, AUTO_CLEANUP_DAYS",
            parse_mode=ParseMode.HTML
        )
        return
    key = context.args[0].strip()
    value = " ".join(context.args[1:]).strip()
    try:
        await set_cfg(key, value)
        await update.message.reply_text(f"✅ Đã cập nhật: <code>{esc(key)}</code> = <code>{esc(value)}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"setconfig_command error: {e}")

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
    desc = " ".join(context.args[2:]).strip() if len(context.args) > 2 else None
    try:
        await set_model_price(model, price, 1, desc)
        await update.message.reply_text(f"✅ Đã cập nhật giá: <code>{esc(model)}</code> = {price} req", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"setprice_command error: {e}")

async def admin_models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        prices = await get_model_prices()
        text = "🤖 <b>Quản Lý Model:</b>\n\n"
        for k, v in prices.items():
            status = "✅ BẬT" if v["enabled"] else "❌ TẮT"
            desc = f" — {esc(v['description'])}" if v['description'] else ""
            text += f"• <code>{esc(k)}</code> | {v['price']} req | {status}{desc}\n"
        text += "\nDùng <code>/togglemodel [tên]</code> để bật/tắt."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"admin_models_command error: {e}")

async def togglemodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/togglemodel deepseek-v4-flash</code>", parse_mode=ParseMode.HTML)
        return
    model = " ".join(context.args).strip()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT enabled FROM model_prices WHERE model_name = ?", (model,))
            row = await cur.fetchone()
            if not row:
                await update.message.reply_text("❌ Model không tồn tại.")
                return
            new_state = 0 if row[0] else 1
            await db.execute("UPDATE model_prices SET enabled = ? WHERE model_name = ?", (new_state, model))
            await db.commit()
        await update.message.reply_text(f"✅ Model <code>{esc(model)}</code> đã {'BẬT' if new_state else 'TẮT'}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"togglemodel_command error: {e}")

async def admin_prompts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        prompts = await get_all_prompts()
        text = "🎭 <b>Quản Lý Prompt:</b>\n\n"
        for p in prompts:
            status = "✅ BẬT" if p[2] else "❌ TẮT"
            text += f"• <b>{p[0]}</b> | {status}\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"admin_prompts_command error: {e}")

async def addprompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Ví dụ: <code>/addprompt funny Bạn là hài hước...</code>", parse_mode=ParseMode.HTML)
        return
    name = context.args[0].strip().lower()
    content = " ".join(context.args[1:]).strip()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO prompts (name, content, enabled) VALUES (?, ?, 1)", (name, content))
            await db.commit()
        await update.message.reply_text(f"✅ Đã thêm prompt: <b>{name}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"addprompt_command error: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/broadcast Chào tất cả! Có tin mới...</code>", parse_mode=ParseMode.HTML)
        return
    message = " ".join(context.args)
    try:
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
    except Exception as e:
        logger.error(f"broadcast_command error: {e}")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        cfg = await get_all_cfg()
        current = cfg.get("MAINTENANCE_MODE", "0")
        new_val = "0" if current == "1" else "1"
        await set_cfg("MAINTENANCE_MODE", new_val)
        status = "BẬT" if new_val == "1" else "TẮT"
        await update.message.reply_text(f"🔧 Chế độ bảo trì đã {status}.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"maintenance_command error: {e}")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
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
    except Exception as e:
        logger.error(f"health_command error: {e}")

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        await auto_cleanup()
        await update.message.reply_text("🧹 Đã dọn dẹp dữ liệu cũ.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"cleanup_command error: {e}")

async def feedback_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        fbs = await get_pending_feedback(20)
        if not fbs:
            await update.message.reply_text("✅ Không có feedback nào chờ xử lý.")
            return
        text = "📣 <b>Feedback Chờ Xử Lý:</b>\n\n"
        for f in fbs:
            text += f"#{f[0]} | User <code>{f[1]}</code> | {f[4][:16]}\n{esc(f[3][:200])}\n\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"feedback_list_command error: {e}")

async def feedback_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: <code>/feedbackdone 1 [phản hồi]</code>", parse_mode=ParseMode.HTML)
        return
    try:
        fid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")
        return
    reply = " ".join(context.args[1:]).strip() if len(context.args) > 1 else None
    try:
        await mark_feedback_done(fid, reply)
        await update.message.reply_text(f"✅ Đã đánh dấu feedback #{fid} đã xử lý.")
        if reply:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM feedback WHERE id = ?", (fid,))
                row = await cur.fetchone()
                if row:
                    try:
                        await context.bot.send_message(
                            row[0],
                            f"📬 <b>Phản hồi từ Admin:</b>\n\n{esc(reply)}\n\n"
                            f"Cảm ơn bạn đã góp ý!",
                            parse_mode=ParseMode.HTML
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"feedback_done_command error: {e}")

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["user_id", "username", "first_name", "req_balance", "req_earned", "req_spent", "total_keys", "total_messages", "banned", "created_at", "last_active"])
        us = await get_users_list(10000)
        for u in us:
            writer.writerow([u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7], u[8], u[9], u[10] if len(u) > 10 else ""])
        output.seek(0)
        await update.message.reply_document(
            document=output.getvalue().encode("utf-8-sig"),
            filename=f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            caption="📊 Xuất dữ liệu users thành công."
        )
    except Exception as e:
        logger.error(f"export_command error: {e}")

# ========================
# ADMIN CALLBACK HANDLER
# ========================
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    if not is_admin(query.from_user.id):
        return
    data = query.data

    try:
        if data == "adm_stats":
            s = await get_stats()
            await query.edit_message_text(
                f"📊 <b>Thống Kê</b>\n\n"
                f"👤 Users: {s['total_users']}\n"
                f"💎 Req lưu hành: {s['total_req']}\n"
                f"📤 Req đã dùng: {s['total_spent']}\n"
                f"🔑 Keys đã dùng: {s['total_keys']}\n"
                f"⏳ Keys chờ: {s['pending_keys']}\n"
                f"💬 Tin nhắn: {s['total_messages']}\n"
                f"📅 Hoạt động hôm nay: {s['today_logs']}\n"
                f"📣 Feedback chờ: {s['pending_feedback']}\n"
                f"🚫 Banned: {s['banned_users']}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("adm_menu"))
            )
        elif data == "adm_users":
            us = await get_users_list(10)
            text = "👤 <b>Users (10 gần nhất):</b>\n\n"
            for u in us:
                status = "🚫" if u[7] else "✅"
                name = esc(u[2] or u[1] or str(u[0]))
                text += f"{status} <code>{u[0]}</code> | {name} | 💎{u[3]}\n"
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data == "adm_keys":
            keys = await get_pending_keys(15)
            if not keys:
                text = "✅ Không có key nào đang chờ."
            else:
                text = "🔑 <b>Key chưa dùng (15):</b>\n\n"
                for r in keys:
                    src = "U" if r[2] == "user" else "A"
                    text += f"<code>{esc(r[0])}</code> | {r[1]}r | {src} | {r[3][:16]}\n"
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data == "adm_config":
            cfg = await get_all_cfg()
            text = "⚙️ <b>Config:</b>\n\n"
            for k, v in list(cfg.items())[:15]:
                text += f"• <code>{esc(k)}</code> = <code>{esc(v)}</code>\n"
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data == "adm_broadcast":
            await query.edit_message_text(
                "📢 <b>Broadcast</b>\n\n"
                "Dùng lệnh: <code>/broadcast [nội dung]</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("adm_menu"))
            )
        elif data == "adm_health":
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
            await query.edit_message_text(
                f"🏥 <b>Health Check</b>\n\n" + "\n".join(status),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("adm_menu"))
            )
        elif data == "adm_cleanup":
            await auto_cleanup()
            await query.edit_message_text("🧹 Đã dọn dẹp dữ liệu cũ.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data == "adm_export":
            await query.edit_message_text(
                "📥 <b>Export</b>\n\n"
                "Dùng lệnh: <code>/export</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn("adm_menu"))
            )
        elif data == "adm_menu":
            keyboard = [
                [InlineKeyboardButton("📊 Thống kê", callback_data="adm_stats"), InlineKeyboardButton("👤 Users", callback_data="adm_users")],
                [InlineKeyboardButton("🔑 Keys", callback_data="adm_keys"), InlineKeyboardButton("⚙️ Config", callback_data="adm_config")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"), InlineKeyboardButton("🏥 Health", callback_data="adm_health")],
                [InlineKeyboardButton("🧹 Cleanup", callback_data="adm_cleanup"), InlineKeyboardButton("📥 Export", callback_data="adm_export")],
            ]
            await query.edit_message_text(
                "🔐 <b>ADMIN PANEL</b>\n\nChọn chức năng:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif data.startswith("adm_addreq|"):
            parts = data.split("|")
            tid, amount = int(parts[1]), int(parts[2])
            await admin_add_req(tid, amount, query.from_user.id)
            await query.edit_message_text(f"✅ Đã nạp {amount} req cho user <code>{tid}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data.startswith("adm_ban|"):
            tid = int(data.split("|")[1])
            await admin_ban_user(tid, 1)
            await query.edit_message_text(f"🚫 Đã khóa user <code>{tid}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data.startswith("adm_unban|"):
            tid = int(data.split("|")[1])
            await admin_ban_user(tid, 0)
            await query.edit_message_text(f"✅ Đã mở khóa user <code>{tid}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
        elif data.startswith("adm_logs|"):
            tid = int(data.split("|")[1])
            logs = await get_user_logs(tid, 20)
            text = f"📋 <b>Logs User {tid}:</b>\n\n"
            for l in logs:
                text += f"• {l[2]} | {l[0]} | {esc(l[1])}\n"
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn("adm_menu")))
    except Exception as e:
        logger.error(f"admin_callback_handler error: {e}")
        try:
            await query.edit_message_text("❌ Lỗi xử lý. Vui lòng thử lại.", parse_mode=ParseMode.HTML)
        except Exception:
            pass

# ========================
# ERROR HANDLER
# ========================
async def error_handler(update, context):
    logger.error(f"Exception: {context.error}")
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.", parse_mode=ParseMode.HTML)
        except Exception:
            pass

# ========================
# POST INIT & MAIN
# ========================
async def post_init(app: Application):
    uc = [
        BotCommand("start", "Menu chính"), BotCommand("help", "Hướng dẫn"),
        BotCommand("key", "Nhập key nhận req"), BotCommand("model", "Chọn model AI"),
        BotCommand("prompt", "Chọn tính cách AI"), BotCommand("new", "Xóa lịch sử chat"),
        BotCommand("history", "Xem lịch sử"), BotCommand("profile", "Hồ sơ cá nhân"),
        BotCommand("balance", "Xem số dư"), BotCommand("top", "Bảng xếp hạng"),
        BotCommand("checkin", "Điểm danh nhận req"), BotCommand("ref", "Mã giới thiệu"),
        BotCommand("feedback", "Góp ý cho admin"), BotCommand("mykeys", "Lịch sử key")
    ]
    ac = [
        BotCommand("admin", "Admin Panel"), BotCommand("stats", "Thống kê"), BotCommand("logs", "Xem logs"),
        BotCommand("health", "Kiểm tra hệ thống"), BotCommand("users", "Danh sách users"),
        BotCommand("user", "Chi tiết user"), BotCommand("addreq", "Nạp req"),
        BotCommand("gift", "Tặng req"), BotCommand("genkey", "Tạo key trực tiếp"),
        BotCommand("keys", "Quản lý key"), BotCommand("revoke", "Thu hồi key"),
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

    # User handlers
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
    app.add_handler(CommandHandler("mykeys", mykeys_command))

    # Admin handlers
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("user", user_detail_command))
    app.add_handler(CommandHandler("addreq", addreq_command))
    app.add_handler(CommandHandler("gift", gift_command))
    app.add_handler(CommandHandler("genkey", genkey_command))
    app.add_handler(CommandHandler("keys", admin_keys_command))
    app.add_handler(CommandHandler("revoke", revoke_command))
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

    # Callbacks — admin callbacks first (more specific pattern)
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=r"^adm_"))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    app.add_error_handler(error_handler)

    logger.info("Denia Bot Ultimate v3.0 starting...")
    asyncio.run(init_app())
    logger.info(f"Ready. Admin: {ADMIN_PHONE} | Req/link: {REQ_PER_LINK}")
    if ADMIN_TELEGRAM_ID == 0:
        logger.info("Auto-admin enabled.")
    else:
        logger.info(f"Admin ID: {ADMIN_TELEGRAM_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
