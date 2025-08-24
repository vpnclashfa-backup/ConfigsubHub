import asyncio
import logging
import os
import shutil
from typing import Set, List, Tuple

# ماژول‌های پروژه
from src.config import setup_logging, OUTPUT_DIR, SOURCE_TELEGRAM_FILE
from src.file_handler import (read_source_links, setup_directories, 
                              save_mixed_files, save_source_files)
from src.network_handler import fetch_all_subs
from src.parser import decode_content, parse_nodes, categorize_nodes
from src.telegram_handler import normalize_channel_id, scrape_channel

def clean_output_directory():
    """
    پوشه خروجی را در صورت وجود حذف می‌کند تا از باقی ماندن فایل‌های قدیمی جلوگیری شود.
    """
    if os.path.exists(OUTPUT_DIR):
        logging.info(f"در حال پاک‌سازی پوشه خروجی قدیمی: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

def read_telegram_channels() -> List[str]:
    """
    شناسه‌های کانال‌های تلگرام را از فایل منبع می‌خواند.
    """
    channels = []
    try:
        with open(SOURCE_TELEGRAM_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                channel_id = normalize_channel_id(line)
                if channel_id:
                    channels.append(channel_id)
    except FileNotFoundError:
        logging.info(f"فایل منبع تلگرام یافت نشد: {SOURCE_TELEGRAM_FILE}. از این منبع صرف‌نظر می‌شود.")
        # ایجاد فایل خالی برای استفاده‌های بعدی
        open(SOURCE_TELEGRAM_FILE, 'w').close()
    return list(set(channels)) # حذف موارد تکراری

async def process_subscription_links(all_nodes_set: Set[str]):
    """
    لینک‌های اشتراک معمولی را پردازش می‌کند.
    """
    links = read_source_links()
    if not links:
        logging.info("هیچ لینک اشتراک معمولی برای پردازش یافت نشد.")
        return
        
    logging.info(f"تعداد {len(links)} لینک اشتراک برای پردازش یافت شد.")
    results = await fetch_all_subs(links)
    logging.info("دانلود محتوای لینک‌های اشتراک به پایان رسید.")
    
    for name, content in results:
        if not content:
            logging.warning(f"محتوایی برای '{name}' دریافت نشد، از این لینک صرف‌نظر می‌شود.")
            continue
            
        logging.info(f"در حال پردازش محتوای '{name}'...")
        decoded_content = decode_content(content)
        source_nodes = parse_nodes(decoded_content)
        
        if not source_nodes:
            logging.warning(f"هیچ نود معتبری در '{name}' یافت نشد.")
            continue
            
        logging.info(f"تعداد {len(source_nodes)} نود در '{name}' پیدا شد.")
        categorized_source_nodes = categorize_nodes(source_nodes)
        await save_source_files(name, categorized_source_nodes)
        all_nodes_set.update(source_nodes)

async def process_telegram_channels(all_nodes_set: Set[str]):
    """
    کانال‌های تلگرام را پردازش می‌کند.
    """
    channel_ids = read_telegram_channels()
    if not channel_ids:
        logging.info("هیچ کانال تلگرامی برای پردازش یافت نشد.")
        return

    logging.info(f"تعداد {len(channel_ids)} کانال تلگرام برای پردازش یافت شد.")
    
    # نکته: اسکرپ کردن تلگرام یک عملیات I/O-bound سنکرون است.
    # برای جلوگیری از بلاک شدن کامل، می‌توان آن را در یک executor اجرا کرد.
    # اما برای سادگی فعلی، آن را به صورت متوالی اجرا می‌کنیم.
    for channel_id in channel_ids:
        # نام منبع همان شناسه کانال خواهد بود
        name = channel_id
        source_nodes = scrape_channel(channel_id)
        
        if not source_nodes:
            logging.warning(f"هیچ نود معتبری در کانال '{name}' یافت نشد.")
            continue
            
        logging.info(f"تعداد {len(source_nodes)} نود در کانال '{name}' پیدا شد.")
        categorized_source_nodes = categorize_nodes(source_nodes)
        await save_source_files(name, categorized_source_nodes)
        all_nodes_set.update(source_nodes)

async def main():
    """
    نقطه شروع و تابع اصلی اجرای برنامه
    """
    setup_logging()
    
    clean_output_directory()
    logging.info("برنامه شروع به کار کرد. در حال آماده‌سازی پوشه‌های خروجی...")
    setup_directories()
    logging.info("پوشه‌های خروجی با موفقیت ساخته شدند.")
    
    all_nodes_set: Set[str] = set()

    # --- بخش اول: پردازش لینک‌های اشتراک ---
    await process_subscription_links(all_nodes_set)
    
    # --- بخش دوم: پردازش کانال‌های تلگرام ---
    await process_telegram_channels(all_nodes_set)

    # --- بخش نهایی: ساخت فایل‌های میکس ---
    if all_nodes_set:
        all_nodes_list = sorted(list(all_nodes_set)) # مرتب‌سازی برای خروجی یکنواخت
        logging.info(f"در مجموع {len(all_nodes_list)} نود منحصر به فرد برای ساخت فایل میکس جمع‌آوری شد.")
        categorized_all_nodes = categorize_nodes(all_nodes_list)
        await save_mixed_files(categorized_all_nodes)
        logging.info("فایل‌های میکس با موفقیت ساخته شدند.")
    else:
        logging.warning("هیچ نودی برای ساخت فایل میکس وجود ندارد.")
        
    logging.info("عملیات با موفقیت به پایان رسید.")


if __name__ == "__main__":
    asyncio.run(main())
