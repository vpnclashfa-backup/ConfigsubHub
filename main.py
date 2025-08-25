import asyncio
import logging
import os
from typing import Set

import aiohttp

# ماژول‌های پروژه
from src.config import setup_logging, SOURCE_LINK_DIR, SOURCE_TELEGRAM_DIR
from src.file_handler import (
    read_source_links, setup_directories, save_mixed_files, 
    save_source_files, clean_output_directory, read_telegram_channels,
    update_telegram_source_file
)
from src.network_handler import fetch_all_subs
from src.parser import decode_content, parse_nodes, categorize_nodes
from src.telegram_handler import scrape_channel

async def process_subscription_links(session: aiohttp.ClientSession, all_nodes_set: Set[str]):
    """لینک‌های اشتراک معمولی را پردازش کرده و نتایج را ذخیره می‌کند."""
    links = read_source_links()
    if not links:
        logging.info("هیچ لینک اشتراک معمولی برای پردازش یافت نشد.")
        return
        
    logging.info(f"تعداد {len(links)} لینک اشتراک برای پردازش یافت شد.")
    results = await fetch_all_subs(session, links)
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
            
        logging.info(f"تعداد {len(source_nodes)} نود معتبر از '{name}' استخراج شد.")
        categorized_source_nodes = categorize_nodes(source_nodes)
        await save_source_files(SOURCE_LINK_DIR, name, categorized_source_nodes)
        all_nodes_set.update(source_nodes)

async def process_telegram_channels(session: aiohttp.ClientSession, all_nodes_set: Set[str]):
    """کانال‌های تلگرام را به صورت موازی پردازش کرده و نتایج را ذخیره می‌کند."""
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
            # لاگ مربوطه در خود تابع scrape_channel ثبت شده است
            continue
            
        categorized_source_nodes = categorize_nodes(source_nodes)
        await save_source_files(SOURCE_TELEGRAM_DIR, channel_id, categorized_source_nodes)
        all_nodes_set.update(source_nodes)
    
    # فایل منبع تلگرام را فقط با کانال‌های معتبر به‌روزرسانی می‌کنیم
    update_telegram_source_file(valid_channels)

async def main():
    """نقطه شروع و تابع اصلی اجرای برنامه."""
    setup_logging()
    
    # 1. آماده‌سازی محیط
    clean_output_directory()
    setup_directories()
    logging.info("برنامه شروع به کار کرد. پوشه‌های خروجی آماده شدند.")
    
    all_nodes_set: Set[str] = set()
    
    # 2. پردازش منابع به صورت موازی
    async with aiohttp.ClientSession() as session:
        await process_subscription_links(session, all_nodes_set)
        await process_telegram_channels(session, all_nodes_set)

    # 3. تجمیع و ذخیره نتایج نهایی
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
    # For Windows, to avoid "Event loop is closed" RuntimeError on Ctrl+C.
    # This policy is only available and needed on Windows.
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
