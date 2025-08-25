import os
import logging

# --- Path Configuration ---
# مسیر ریشه پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# مسیرهای فایل ورودی
SOURCE_DIR = os.path.join(BASE_DIR, "source")
SOURCE_NORMAL_FILE = os.path.join(SOURCE_DIR, "normal_sub_link")
SOURCE_TELEGRAM_FILE = os.path.join(SOURCE_DIR, "telegram")

# مسیر پوشه خروجی اصلی
OUTPUT_DIR = os.path.join(BASE_DIR, "sub")

# مسیرهای زیرپوشه‌های خروجی عمومی
MIX_DIR = os.path.join(OUTPUT_DIR, "mix")
MIX_BASE64_DIR = os.path.join(MIX_DIR, "base64")

SOURCE_SPECIFIC_DIR = os.path.join(OUTPUT_DIR, "source")

# مسیرهای خروجی منابع مجزا
SOURCE_LINK_DIR = os.path.join(SOURCE_SPECIFIC_DIR, "link")
SOURCE_TELEGRAM_DIR = os.path.join(SOURCE_SPECIFIC_DIR, "telegram")

# --- Network Configuration ---
# هدرهای HTTP برای شبیه‌سازی یک مرورگر واقعی
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# حداکثر زمان انتظار برای هر درخواست (به ثانیه)
REQUEST_TIMEOUT = 30

# --- Telegram Scraper Configuration ---
# حداکثر عمر پست‌ها برای بررسی (به روز)
TELEGRAM_POST_MAX_AGE_DAYS = 7


# --- File Naming Configuration ---
MIX_ALL_FILE_NAME = "all.txt"
MIX_ANYTLS_FILE_NAME = "anytls.txt"
MIX_HTTP_PROXY_FILE_NAME = "http.txt"
MIX_HTTPS_PROXY_FILE_NAME = "https.txt" # متغیر برای پراکسی HTTPS
MIX_HYSTERIA_FILE_NAME = "hysteria.txt"
MIX_HY2_FILE_NAME = "hy2.txt"
MIX_JUICITY_FILE_NAME = "juicity.txt"
MIX_MIERU_FILE_NAME = "mieru.txt"
MIX_MTPROTO_FILE_NAME = "mtproto.txt"
MIX_SNELL_FILE_NAME = "snell.txt"
MIX_SOCKS4_FILE_NAME = "socks4.txt"
MIX_SOCKS5_FILE_NAME = "socks5.txt"
MIX_SS_FILE_NAME = "ss.txt"
MIX_SSR_FILE_NAME = "ssr.txt"
MIX_SSH_FILE_NAME = "ssh.txt"
MIX_TROJAN_FILE_NAME = "trojan.txt"
MIX_TUIC_FILE_NAME = "tuic.txt"
MIX_VLESS_FILE_NAME = "vless.txt"
MIX_VMESS_FILE_NAME = "vmess.txt"
MIX_WARP_FILE_NAME = "warp.txt"
MIX_WIREGUARD_FILE_NAME = "wireguard.txt"


# --- Logging Configuration ---
def setup_logging():
    """
    پیکربندی سیستم لاگ‌گیری برای نمایش پیام‌ها در کنسول.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
