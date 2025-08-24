import asyncio
import logging
import os
import shutil
from typing import Set

# ماژول‌های پروژه
from src.config import setup_logging, OUTPUT_DIR
from src.file_handler import (read_source_links, setup_directories, 
                              save_mixed_files, save_source_files)
from src.network_handler import fetch_all_subs
from src.parser import decode_content, parse_nodes, categorize_nodes

def clean_output_directory():
    """
    پوشه خروجی را در صورت وجود حذف می‌کند تا از باقی ماندن فایل‌های قدیمی جلوگیری شود.
    """
    if os.path.exists(OUTPUT_DIR):
        logging.info(f"در حال پاک‌سازی پوشه خروجی قدیمی: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

async def main():
    """
    نقطه شروع و تابع اصلی اجرای برنامه
    """
    setup_logging()
    
    # 0. پاک‌سازی پوشه خروجی قبل از شروع
    clean_output_directory()
    
    logging.info("برنامه شروع به کار کرد. در حال آماده‌سازی پوشه‌های خروجی...")
    
    # 1. ساخت پوشه‌های مورد نیاز برای خروجی
    setup_directories()
    logging.info("پوشه‌های خروجی با موفقیت ساخته شدند.")
    
    # 2. خواندن لینک‌ها از فایل منبع
    links = read_source_links()
    if not links:
        logging.warning("هیچ لینکی در فایل منبع یافت نشد. برنامه خاتمه می‌یابد.")
        return
    logging.info(f"تعداد {len(links)} لینک برای پردازش یافت شد.")
    
    # 3. دانلود محتوای همه لینک‌ها به صورت آسنکرون و موازی
    results = await fetch_all_subs(links)
    logging.info("دانلود محتوای لینک‌ها به پایان رسید.")
    
    # استفاده از set برای جلوگیری از ذخیره نودهای تکراری
    all_nodes_set: Set[str] = set()
    
    # 4. پردازش هر لینک دانلود شده
    for name, content in results:
        if not content:
            logging.warning(f"محتوایی برای '{name}' دریافت نشد، از این لینک صرف‌نظر می‌شود.")
            continue
            
        logging.info(f"در حال پردازش محتوای '{name}'...")
        
        # 4.1. تشخیص و رمزگشایی محتوای Base64
        decoded_content = decode_content(content)
        
        # 4.2. استخراج نودها (لینک‌های کانفیگ) از محتوای متنی
        source_nodes = parse_nodes(decoded_content)
        if not source_nodes:
            logging.warning(f"هیچ نود معتبری در '{name}' یافت نشد.")
            continue
        
        logging.info(f"تعداد {len(source_nodes)} نود در '{name}' پیدا شد.")
        
        # 4.3. دسته‌بندی نودها بر اساس پروتکل
        categorized_source_nodes = categorize_nodes(source_nodes)
        
        # 4.4. ذخیره فایل‌های مخصوص این لینک (عادی و Base64)
        await save_source_files(name, categorized_source_nodes)
        
        # 4.5. اضافه کردن نودهای این منبع به مجموعه کلی نودها (حذف تکراری خودکار)
        all_nodes_set.update(source_nodes)

    # 5. پردازش و ذخیره فایل‌های میکس (ترکیب همه لینک‌ها)
    if all_nodes_set:
        all_nodes_list = list(all_nodes_set)
        logging.info(f"در مجموع {len(all_nodes_list)} نود منحصر به فرد برای ساخت فایل میکس جمع‌آوری شد.")
        categorized_all_nodes = categorize_nodes(all_nodes_list)
        await save_mixed_files(categorized_all_nodes)
        logging.info("فایل‌های میکس با موفقیت ساخته شدند.")
    else:
        logging.warning("هیچ نودی برای ساخت فایل میکس وجود ندارد.")
        
    logging.info("عملیات با موفقیت به پایان رسید.")


if __name__ == "__main__":
    asyncio.run(main())
