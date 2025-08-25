import logging
import os
import re
import shutil
import base64
from typing import List, Tuple, Dict

import aiofiles

from .config import (
    OUTPUT_DIR, SOURCE_NORMAL_FILE, SOURCE_TELEGRAM_FILE, MIX_DIR, 
    SOURCE_LINK_DIR, SOURCE_TELEGRAM_DIR, MIX_ALL_FILE_NAME, 
    MIX_ANYTLS_FILE_NAME, MIX_HTTP_PROXY_FILE_NAME, MIX_HTTPS_PROXY_FILE_NAME, 
    MIX_HYSTERIA_FILE_NAME, MIX_HY2_FILE_NAME, MIX_JUICITY_FILE_NAME, 
    MIX_MIERU_FILE_NAME, MIX_MTPROTO_FILE_NAME, MIX_SNELL_FILE_NAME, 
    MIX_SOCKS4_FILE_NAME, MIX_SOCKS5_FILE_NAME, MIX_SS_FILE_NAME, 
    MIX_SSR_FILE_NAME, MIX_SSH_FILE_NAME, MIX_TROJAN_FILE_NAME, 
    MIX_TUIC_FILE_NAME, MIX_VLESS_FILE_NAME, MIX_VMESS_FILE_NAME, 
    MIX_WARP_FILE_NAME, MIX_WIREGUARD_FILE_NAME
)
from .telegram_handler import normalize_channel_id

# نگاشت پروتکل به نام فایل خروجی
PROTOCOL_TO_FILENAME = {
    "all": MIX_ALL_FILE_NAME,
    "anytls": MIX_ANYTLS_FILE_NAME,
    "http": MIX_HTTP_PROXY_FILE_NAME,
    "https": MIX_HTTPS_PROXY_FILE_NAME, # اضافه شد برای پشتیبانی از فایل جداگانه
    "hysteria": MIX_HYSTERIA_FILE_NAME,
    "hy2": MIX_HY2_FILE_NAME,
    "juicity": MIX_JUICITY_FILE_NAME,
    "mieru": MIX_MIERU_FILE_NAME,
    "mtproto": MIX_MTPROTO_FILE_NAME,
    "snell": MIX_SNELL_FILE_NAME,
    "socks4": MIX_SOCKS4_FILE_NAME,
    "socks5": MIX_SOCKS5_FILE_NAME,
    "ss": MIX_SS_FILE_NAME,
    "ssr": MIX_SSR_FILE_NAME,
    "ssh": MIX_SSH_FILE_NAME,
    "trojan": MIX_TROJAN_FILE_NAME,
    "tuic": MIX_TUIC_FILE_NAME,
    "vless": MIX_VLESS_FILE_NAME,
    "vmess": MIX_VMESS_FILE_NAME,
    "warp": MIX_WARP_FILE_NAME,
    "wireguard": MIX_WIREGUARD_FILE_NAME,
}

def clean_output_directory():
    """پوشه خروجی را در صورت وجود حذف و پاک‌سازی می‌کند."""
    if os.path.exists(OUTPUT_DIR):
        logging.info(f"در حال پاک‌سازی پوشه خروجی قدیمی: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

def setup_directories():
    """پوشه‌های خروجی مورد نیاز را ایجاد می‌کند."""
    dirs_to_create = [
        MIX_DIR, os.path.join(MIX_DIR, "base64"),
        SOURCE_LINK_DIR, SOURCE_TELEGRAM_DIR
    ]
    for directory in dirs_to_create:
        os.makedirs(directory, exist_ok=True)
    logging.info("تمام پوشه‌های خروجی با موفقیت بررسی و ایجاد شدند.")

def read_source_links() -> List[Tuple[str, str]]:
    """لینک‌های اشتراک را از فایل منبع با فرمت URL|Name می‌خواند."""
    links = []
    try:
        with open(SOURCE_NORMAL_FILE, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('|', 1)
                url = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else f"link_{i:03d}"
                
                if url:
                    links.append((name, url))

    except FileNotFoundError:
        logging.info(f"فایل منبع لینک‌ها یافت نشد: {SOURCE_NORMAL_FILE}. یک فایل خالی ایجاد می‌شود.")
        os.makedirs(os.path.dirname(SOURCE_NORMAL_FILE), exist_ok=True)
        open(SOURCE_NORMAL_FILE, 'w').close()
    return links

def read_telegram_channels() -> List[str]:
    """شناسه‌های کانال‌های تلگرام را از فایل منبع می‌خواند و نرمال‌سازی می‌کند."""
    channels = []
    try:
        with open(SOURCE_TELEGRAM_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                channel_id = normalize_channel_id(line)
                if channel_id:
                    channels.append(channel_id)
    except FileNotFoundError:
        logging.info(f"فایل منبع تلگرام یافت نشد: {SOURCE_TELEGRAM_FILE}. یک فایل خالی ایجاد می‌شود.")
        os.makedirs(os.path.dirname(SOURCE_TELEGRAM_FILE), exist_ok=True)
        open(SOURCE_TELEGRAM_FILE, 'w').close()
    return list(set(channels))

def update_telegram_source_file(valid_channels: List[str]):
    """فایل منبع تلگرام را فقط با شناسه‌های معتبر بازنویسی می‌کند."""
    if not valid_channels:
        logging.warning("هیچ کانال تلگرام معتبری برای ذخیره یافت نشد. فایل منبع خالی خواهد شد.")
    
    try:
        sorted_channels = sorted(list(set(valid_channels)))
        with open(SOURCE_TELEGRAM_FILE, 'w', encoding='utf-8') as f:
            f.write("# Updated by script: Only valid and existing channels are kept.\n")
            for channel_id in sorted_channels:
                f.write(f"{channel_id}\n")
        logging.info(f"فایل منبع تلگرام با {len(sorted_channels)} کانال معتبر به‌روز شد.")
    except IOError as e:
        logging.error(f"خطا در نوشتن فایل منبع تلگرام: {e}")

async def save_file(path: str, content: str):
    """محتوا را به صورت آسنکرون در یک فایل ذخیره می‌کند."""
    try:
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(content)
        logging.debug(f"فایل با موفقیت در مسیر {path} ذخیره شد.")
    except IOError as e:
        logging.error(f"خطا در نوشتن فایل {path}: {e}")

async def _save_categorized_nodes(base_dir: str, categorized_nodes: Dict[str, List[str]], save_base64: bool):
    """تابع کمکی برای ذخیره نودهای دسته‌بندی شده در یک پوشه مشخص."""
    all_nodes = [node for nodes in categorized_nodes.values() for node in nodes]
    if all_nodes:
        categorized_nodes["all"] = sorted(list(set(all_nodes)))

    for protocol, nodes in categorized_nodes.items():
        filename = PROTOCOL_TO_FILENAME.get(protocol)
        if not filename or not nodes:
            continue
        content = "\n".join(nodes)
        await save_file(os.path.join(base_dir, filename), content)
        if save_base64:
            base64_dir = os.path.join(base_dir, "base64")
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
            await save_file(os.path.join(base64_dir, filename), encoded_content)

async def save_mixed_files(categorized_nodes: Dict[str, List[str]]):
    """فایل‌های میکس (معمولی و Base64) را بر اساس دسته‌بندی ذخیره می‌کند."""
    logging.info(f"در حال ذخیره‌سازی فایل‌های میکس در پوشه: {MIX_DIR}")
    await _save_categorized_nodes(MIX_DIR, categorized_nodes, save_base64=True)

async def save_source_files(base_dir: str, source_name: str, categorized_nodes: Dict[str, List[str]]):
    """فایل‌های خروجی را برای یک منبع خاص (لینک یا کانال تلگرام) ذخیره می‌کند."""
    safe_source_name = re.sub(r'[^\w\d\-_\. ]', '_', source_name).strip() or "unnamed_source"
    source_output_dir = os.path.join(base_dir, safe_source_name)
    os.makedirs(source_output_dir, exist_ok=True)
    logging.info(f"در حال ذخیره‌سازی فایل‌های منبع '{source_name}' در پوشه: {source_output_dir}")
    await _save_categorized_nodes(source_output_dir, categorized_nodes, save_base64=False)
