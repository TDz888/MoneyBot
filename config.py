import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # AI
    AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.xah.io/v1/chat/completions")
    AI_API_KEY = os.getenv("AI_API_KEY")
    AI_MODEL = os.getenv("AI_MODEL", "mistral-medium-3.5-128b")
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "8192"))
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "300"))
    
    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_NAME = os.getenv("BOT_NAME", "Denia Pharmacist")
    
    # Research
    MAX_RESEARCH_STEPS = int(os.getenv("MAX_RESEARCH_STEPS", "15"))
    ENABLE_DEEP_RESEARCH = os.getenv("ENABLE_DEEP_RESEARCH", "true").lower() == "true"
    RESEARCH_TEMPERATURE = float(os.getenv("RESEARCH_TEMPERATURE", "0.2"))
    ENABLE_SELF_CORRECTION = os.getenv("ENABLE_SELF_CORRECTION", "true").lower() == "true"
    
    # System
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
    TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", "0"))  # 0 = no timeout
    
    @staticmethod
    def validate():
        assert Config.AI_API_KEY, "AI_API_KEY missing"
        assert Config.BOT_TOKEN, "BOT_TOKEN missing"
