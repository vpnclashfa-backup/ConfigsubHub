import asyncio
import logging
import os
import shutil
from typing import Set, List, Tuple

import aiohttp

# ماژول‌های پروژه
from src.config import setup_logging, OUTPUT_DIR, SOURCE_TELEGRAM_FILE, SOURCE_LINK_DIR, SOURCE_TELEGRAM_DIR
from src.file_handler import (read_source_links, setup_directories, 
                              save_mixed_files, save_source_files)
from src.network_handler import fetch_all_subs
from src.parser import decode_content, parse_nodes, categorize_nodes
from src.telegram_handler import normalize_channel_id, scrape_channel

def clean_output_directory():
    """پوشه خروجی را در صورت وجود حذف می‌کند."""
    if os.path.exists(OUTPUT_DIR):
        logging.info(f"در حال پاک‌سازی پوشه خروجی قدیمی: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

def read_telegram_channels() -> List[str]:
    """شناسه‌های کانال‌های تلگرام را از فایل منبع می‌خواند."""
    channels = []
    try:
        with open(SOURCE_TELEGRAM_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                channel_id = normalize_channel_id(line)
                if channel_id:
                    channels.append(channel_id)
    except FileNotFoundError:
        logging.info(f"فایل منبع تلگرام یافت نشد: {SOURCE_TELEGRAM_FILE}. از این منبع صرف‌نظر می‌شود.")
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

async def process_subscription_links(session: aiohttp.ClientSession, all_nodes_set: Set[str]):
    """لینک‌های اشتراک معمولی را پردازش می‌کند."""
    links = read_source_links()
    if not links:
        logging.info("هیچ لینک اشتراک معمولی برای پردازش یافت نشد.")
        return
        
    logging.info(f"تعداد {len(links)} لینک اشتراک برای پردازش یافت شد.")
    results = await fetch_all_subs(session, links) # ارسال سشن به تابع
    logging.info("دانلود محتوای لینک‌های اشتراک به پایان رسید.")
    
    for name, content in results:
        if not content:
            logging.warning(f"محتوایی برای '{name}' دریافت نشد، از این لینک صرف‌نظر می‌شود.")
            continue
        
        decoded_content = decode_content(content)
        source_nodes = parse_nodes(decoded_content)
        if not source_nodes:
            logging.warning(f"هیچ نود معتبری در '{name}' یافت نشد.")
            continue
            
        categorized_source_nodes = categorize_nodes(source_nodes)
        await save_source_files(SOURCE_LINK_DIR, name, categorized_source_nodes)
        all_nodes_set.update(source_nodes)

async def process_telegram_channels(session: aiohttp.ClientSession, all_nodes_set: Set[str]):
    """کانال‌های تلگرام را به صورت موازی پردازش می‌کند."""
    channel_ids = read_telegram_channels()
    if not channel_ids:
        logging.info("هیچ کانال تلگرامی برای پردازش یافت نشد.")
        return

    logging.info(f"تعداد {len(channel_ids)} کانال تلگرام برای پردازش یافت شد. شروع اسکرپ موازی...")
    
    tasks = [scrape_channel(session, channel_id) for channel_id in channel_ids]
    results = await asyncio.gather(*tasks)
    
    valid_channels = []
    for (source_nodes, is_valid), channel_id in zip(results, channel_ids):
        if is_valid:
            valid_channels.append(channel_id)
        
        if not source_nodes:
            continue # لاگ مربوطه در خود تابع scrape_channel ثبت شده است
            
        categorized_source_nodes = categorize_nodes(source_nodes)
        await save_source_files(SOURCE_TELEGRAM_DIR, channel_id, categorized_source_nodes)
        all_nodes_set.update(source_nodes)
    
    update_telegram_source_file(valid_channels)

async def main():
    """نقطه شروع و تابع اصلی اجرای برنامه."""
    setup_logging()
    
    clean_output_directory()
    logging.info("برنامه شروع به کار کرد. در حال آماده‌سازی پوشه‌های خروجی...")
    setup_directories()
    
    all_nodes_set: Set[str] = set()
    
    async with aiohttp.ClientSession() as session:
        await process_subscription_links(session, all_nodes_set)
        await process_telegram_channels(session, all_nodes_set)

    if all_nodes_set:
        all_nodes_list = sorted(list(all_nodes_set))
        logging.info(f"در مجموع {len(all_nodes_list)} نود منحصر به فرد برای ساخت فایل میکس جمع‌آوری شد.")
        categorized_all_nodes = categorize_nodes(all_nodes_list)
        await save_mixed_files(categorized_all_nodes)
        logging.info("فایل‌های میکس با موفقیت ساخته شدند.")
    else:
        logging.warning("هیچ نودی برای ساخت فایل میکس وجود ندارد.")
        
    logging.info("عملیات با موفقیت به پایان رسید.")

if __name__ == "__main__":
    asyncio.run(main())
