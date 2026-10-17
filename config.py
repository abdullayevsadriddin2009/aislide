import os
# ===== Bot token =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "8863758833:AAGOo38f5EyymLztgvL9dw94xB4oZtfT7bE")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@Talaba_AI_SlideBot")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6377032074"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "@support")
# ===== Ma'lumotlar bazasi =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Renderda doimiy disk ulangan bo'lsa: DATA_DIR=/var/data  (aks holda DB har deployda qayta yoziladi)
DATA_DIR = os.getenv("DATA_DIR", BASE_DIR)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = BASE_DIR
DB_PATH = os.path.join(DATA_DIR, "bot_database.db")
# ===== AI API (freellmapi) =====
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://127.0.0.1:31415")
AI_API_URL = AI_BASE_URL
AI_API_KEY = os.getenv("AI_API_KEY", "freellmapi-3152adfb01a3283afee590e02c449d1454c914868f248af5")
AI_MODEL = os.getenv("AI_MODEL", "auto")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))
# ===== Proxy (Telegram bloklangan bo'lsa) =====
PROXY_URL = os.getenv("PROXY_URL", "")
# ===== Web admin panel =====
# Render avtomatik PORT env beradi — shuni o'qiymiz. Lokalda 5000 ishlaydi.
WEB_ADMIN_HOST = os.getenv("WEB_ADMIN_HOST", "0.0.0.0")
WEB_ADMIN_PORT = int(os.getenv("PORT", os.getenv("WEB_ADMIN_PORT", "5000")))
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "admin123")
# ===== To'lov =====
FREE_MODE = os.getenv("FREE_MODE", "1") == "1"
DEFAULT_PAYMENT_INFO = os.getenv("DEFAULT_PAYMENT_INFO", "Humo: 9860 0000 0000 0000")
MIN_TOPUP = int(os.getenv("MIN_TOPUP", "1000"))
# ===== Referal =====
DEFAULT_REFERRAL_BONUS = int(os.getenv("DEFAULT_REFERRAL_BONUS", "500"))
REQUIRE_CHANNEL_SUBSCRIPTION = os.getenv("REQUIRE_CHANNEL_SUBSCRIPTION", "0") == "1"
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@channel")
