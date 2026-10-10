# config.py —— 统一从环境变量读取配置，绝不硬编码密钥
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get(*names, default=None):
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


# ===== LLM =====
OPENAI_API_KEY  = _get("DEEPSEEK_API_KEY", "OPENAI_API_KEY")
OPENAI_BASE_URL = _get("DEEPSEEK_BASE_URL", "OPENAI_BASE_URL",
                       default="https://api.deepseek.com/v1")
MODEL           = _get("DEEPSEEK_MODEL", "MODEL", default="deepseek-chat")

# ===== Agent =====
MAX_STEPS       = int(os.getenv("MAX_STEPS", "25"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", "2"))

# ===== 工作区 & 数据库 =====
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()
DB_PATH       = Path(os.getenv("DB_PATH", "./workspace/data/agent.db")).resolve()

# ===== 邮件（可选）=====
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


def ensure_dirs():
    for sub in ["prefs", "briefings", "cache", "outbox", "data"]:
        (WORKSPACE_DIR / sub).mkdir(parents=True, exist_ok=True)


def mask(secret: str) -> str:
    if not secret:
        return "(空)"
    return secret[:6] + "*" * (len(secret) - 6) if len(secret) > 6 else "***"


ensure_dirs()