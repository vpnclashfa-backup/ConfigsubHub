import os
import logging
import base64
from typing import List, Dict

import aiofiles

# وارد کردن تنظیمات از config.py
from .config import (
    SOURCE_NORMAL_FILE, OUTPUT_DIR, MIX_DIR, MIX_BASE64_DIR, SOURCE_SPECIFIC_DIR,
    SOURCE_LINK_DIR, SOURCE_TELEGRAM_DIR, # وارد کردن مسیرهای جدید
    # وارد کردن همه نام‌های فایل میکس برای استفاده در توابع ذخیره‌سازی
    MIX_ALL_FILE_NAME, MIX_ANYTLS_FILE_NAME, MIX_HTTP_PROXY_FILE_NAME, 
    MIX_HTTPS_PROXY_FILE_NAME, MIX_HYSTERIA_FILE_NAME, MIX_HY2_FILE_NAME,
    MIX_JUICITY_FILE_NAME, MIX_MIERU_FILE_NAME, MIX_MTPROTO_FILE_NAME,
    MIX_SNELL_FILE_NAME, MIX_SOCKS4_FILE_NAME, MIX_SOCKS5_FILE_NAME,
    MIX_SS_FILE_NAME, MIX_SSR_FILE_NAME, MIX_SSH_FILE_NAME, MIX_TROJAN_FILE_NAME,
    MIX_TUIC_FILE_NAME, MIX_VLESS_FILE_NAME, MIX_VMESS_FILE_NAME,
    MIX_WARP_FILE_NAME, MIX_WIREGUARD_FILE_NAME
)

# مپ کردن نوع پروتکل به نام فایل مربوطه
PROTOCOL_TO_FILENAME_MAP = {
    "anytls": MIX_ANYTLS_FILE_NAME,
    "http": MIX_HTTP_PROXY_FILE_NAME,
    "https": MIX_HTTPS_PROXY_FILE_NAME,
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
    """
    پوشه‌های خروجی مورد نیاز را در صورت عدم وجود ایجاد می‌کند.
    """
    os.makedirs(MIX_DIR, exist_ok=True)
    os.makedirs(MIX_BASE64_DIR, exist_ok=True)
    os.makedirs(SOURCE_SPECIFIC_DIR, exist_ok=True)
    # ایجاد زیرپوشه‌های جدید
    os.makedirs(SOURCE_LINK_DIR, exist_ok=True)
    os.makedirs(SOURCE_TELEGRAM_DIR, exist_ok=True)


def read_source_links() -> List[tuple[str, str]]:
    """
    لینک‌ها را از فایل منبع می‌خواند.
    هر خط باید به فرمت 'link|name' باشد.
    
    Returns:
        لیستی از تاپل‌ها که هر کدام شامل (نام، لینک) است.
    """
    links = []
    try:
        with open(SOURCE_NORMAL_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 1)
                link = parts[0].strip()
                name = parts[1].strip()
                if link and name:
                    links.append((name, link))
    except FileNotFoundError:
        logging.error(f"فایل منبع یافت نشد: {SOURCE_NORMAL_FILE}")
        # یک فایل خالی ایجاد می‌کنیم تا در اجرای بعدی برنامه وجود داشته باشد
        open(SOURCE_NORMAL_FILE, 'w').close()
    return links

async def _save_file_and_base64(directory: str, filename: str, content: str):
    """
    یک فایل با محتوای مشخص و نسخه Base64 آن را ذخیره می‌کند.
    """
    if not content:
        return

    # ذخیره فایل عادی
    file_path = os.path.join(directory, filename)
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(content)

    # ذخیره نسخه Base64
    base64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    base64_dir = os.path.join(directory, "base64")
    os.makedirs(base64_dir, exist_ok=True)
    base64_file_path = os.path.join(base64_dir, filename)
    async with aiofiles.open(base64_file_path, 'w', encoding='utf-8') as f:
        await f.write(base64_content)

async def save_mixed_files(categorized_nodes: Dict[str, List[str]]):
    """
    فایل‌های میکس (ترکیبی) را برای همه پروتکل‌ها ذخیره می‌کند.
    """
    all_nodes_content = "\n".join(
        node for nodes in categorized_nodes.values() for node in nodes
    )
    await _save_file_and_base64(MIX_DIR, MIX_ALL_FILE_NAME, all_nodes_content)

    for protocol, nodes in categorized_nodes.items():
        filename = PROTOCOL_TO_FILENAME_MAP.get(protocol)
        if filename:
            content = "\n".join(nodes)
            await _save_file_and_base64(MIX_DIR, filename, content)
    logging.info("ذخیره فایل‌های میکس (عادی و Base64) تکمیل شد.")


async def save_source_files(base_dir: str, source_name: str, categorized_nodes: Dict[str, List[str]]):
    """
    فایل‌های مجزا برای یک منبع خاص را در مسیر پایه مشخص شده ذخیره می‌کند.
    """
    safe_source_name = "".join(c for c in source_name if c.isalnum() or c in (' ', '_')).rstrip()
    source_dir = os.path.join(base_dir, safe_source_name)
    os.makedirs(source_dir, exist_ok=True)
    
    all_nodes_content = "\n".join(
        node for nodes in categorized_nodes.values() for node in nodes
    )
    await _save_file_and_base64(source_dir, MIX_ALL_FILE_NAME, all_nodes_content)
    
    for protocol, nodes in categorized_nodes.items():
        filename = PROTOCOL_TO_FILENAME_MAP.get(protocol)
        if filename:
            content = "\n".join(nodes)
            await _save_file_and_base64(source_dir, filename, content)
    logging.info(f"ذخیره فایل‌های مجزا برای منبع '{source_name}' در مسیر '{base_dir}' تکمیل شد.")
