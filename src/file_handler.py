import logging
import os
import re
import base64
from typing import List, Tuple, Dict

import aiofiles

from .config import (
    SOURCE_NORMAL_FILE, MIX_DIR, SOURCE_LINK_DIR, SOURCE_TELEGRAM_DIR,
    MIX_ALL_FILE_NAME, MIX_ANYTLS_FILE_NAME, MIX_HTTP_PROXY_FILE_NAME,
    MIX_HYSTERIA_FILE_NAME, MIX_HY2_FILE_NAME, MIX_JUICITY_FILE_NAME,
    MIX_MIERU_FILE_NAME, MIX_MTPROTO_FILE_NAME, MIX_SNELL_FILE_NAME,
    MIX_SOCKS4_FILE_NAME, MIX_SOCKS5_FILE_NAME, MIX_SS_FILE_NAME,
    MIX_SSR_FILE_NAME, MIX_SSH_FILE_NAME, MIX_TROJAN_FILE_NAME,
    MIX_TUIC_FILE_NAME, MIX_VLESS_FILE_NAME, MIX_VMESS_FILE_NAME,
    MIX_WARP_FILE_NAME, MIX_WIREGUARD_FILE_NAME
)

# A mapping from protocol name to the desired output file name.
# This helps keep the file saving logic clean and configurable.
PROTOCOL_TO_FILENAME = {
    "all": MIX_ALL_FILE_NAME,
    "anytls": MIX_ANYTLS_FILE_NAME,
    "http": MIX_HTTP_PROXY_FILE_NAME, # Handles both http and https
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

def setup_directories():
    """پوشه‌های خروجی مورد نیاز را ایجاد می‌کند."""
    # Create all necessary directories in one go
    dirs_to_create = [
        os.path.dirname(MIX_DIR), # e.g., 'sub'
        MIX_DIR, 
        os.path.join(MIX_DIR, "base64"),
        SOURCE_LINK_DIR,
        SOURCE_TELEGRAM_DIR
    ]
    for directory in dirs_to_create:
        os.makedirs(directory, exist_ok=True)
    logging.info("تمام پوشه‌های خروجی با موفقیت بررسی و ایجاد شدند.")

def read_source_links() -> List[Tuple[str, str]]:
    """لینک‌های اشتراک را از فایل منبع می‌خواند و برای هرکدام یک نام منحصر به فرد ایجاد می‌کند."""
    links = []
    try:
        with open(SOURCE_NORMAL_FILE, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Create a unique name for each link, e.g., "link_001"
                    name = f"link_{i:03d}"
                    links.append((name, line))
    except FileNotFoundError:
        logging.info(f"فایل منبع لینک‌ها یافت نشد: {SOURCE_NORMAL_FILE}. یک فایل خالی ایجاد می‌شود.")
        # Create the file and its directory if they don't exist.
        os.makedirs(os.path.dirname(SOURCE_NORMAL_FILE), exist_ok=True)
        open(SOURCE_NORMAL_FILE, 'w').close()
    return links

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
    all_nodes = []
    for nodes in categorized_nodes.values():
        all_nodes.extend(nodes)
    
    # اضافه کردن دسته "all" که شامل تمام نودهاست
    if all_nodes:
        categorized_nodes["all"] = sorted(all_nodes)

    for protocol, nodes in categorized_nodes.items():
        filename = PROTOCOL_TO_FILENAME.get(protocol)
        if not filename or not nodes:
            continue

        content = "\n".join(nodes)
        
        # ذخیره فایل عادی
        normal_path = os.path.join(base_dir, filename)
        await save_file(normal_path, content)
        
        if save_base64:
            base64_dir = os.path.join(base_dir, "base64")
            # The directory is already created by setup_directories
            base64_path = os.path.join(base64_dir, filename)
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
            await save_file(base64_path, encoded_content)

async def save_mixed_files(categorized_nodes: Dict[str, List[str]]):
    """فایل‌های میکس (معمولی و Base64) را بر اساس دسته‌بندی ذخیره می‌کند."""
    logging.info(f"در حال ذخیره‌سازی فایل‌های میکس در پوشه: {MIX_DIR}")
    await _save_categorized_nodes(MIX_DIR, categorized_nodes, save_base64=True)

async def save_source_files(base_dir: str, source_name: str, categorized_nodes: Dict[str, List[str]]):
    """فایل‌های خروجی را برای یک منبع خاص (لینک یا کانال تلگرام) ذخیره می‌کند."""
    # پاک‌سازی نام منبع برای استفاده به عنوان نام پوشه
    safe_source_name = re.sub(r'[^\w\d\-_\. ]', '_', source_name).strip()
    if not safe_source_name:
        safe_source_name = "unnamed_source"
        
    source_output_dir = os.path.join(base_dir, safe_source_name)
    os.makedirs(source_output_dir, exist_ok=True)
    
    logging.info(f"در حال ذخیره‌سازی فایل‌های منبع '{source_name}' در پوشه: {source_output_dir}")
    await _save_categorized_nodes(source_output_dir, categorized_nodes, save_base64=False)
