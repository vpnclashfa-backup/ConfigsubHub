import logging
import os
from datetime import datetime
from typing import List

import aiofiles
from bs4 import Tag

from .config import LOG_DIR

async def save_channel_error_log(
    channel_id: str,
    reason: str,
    messages: List[Tag]
):
    """
    یک فایل لاگ برای کانالی که پردازش آن ناموفق بوده است، ذخیره می‌کند.

    Args:
        channel_id: شناسه کانال.
        reason: توضیح متنی دلیل شکست.
        messages: لیستی از تگ‌های BeautifulSoup مربوط به پست‌های بررسی شده.
    """
    try:
        # ایجاد نام فایل بر اساس شناسه کانال و زمان فعلی
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{channel_id}_{timestamp}.log"
        log_filepath = os.path.join(LOG_DIR, log_filename)

        # ساخت محتوای فایل لاگ
        log_content = []
        log_content.append(f"Channel: {channel_id}")
        log_content.append(f"Timestamp: {datetime.now().isoformat()}")
        log_content.append(f"Reason for Failure: {reason}\n")
        log_content.append("="*50)
        log_content.append(" DUMP OF SCANNED MESSAGES (HTML) ")
        log_content.append("="*50 + "\n")

        if messages:
            # اضافه کردن محتوای HTML هر پیام به لاگ
            for i, msg in enumerate(messages, 1):
                log_content.append(f"\n--- Message {i} ---\n")
                log_content.append(msg.prettify()) # .prettify() for readable HTML
        else:
            log_content.append("No messages were available to dump.")

        # نوشتن فایل به صورت آسنکرون
        async with aiofiles.open(log_filepath, 'w', encoding='utf-8') as f:
            await f.write("\n".join(log_content))
        
        logging.info(f"لاگ خطا برای کانال '{channel_id}' در فایل '{log_filename}' ذخیره شد.")

    except Exception as e:
        logging.error(f"خطا در هنگام ذخیره فایل لاگ برای کانال '{channel_id}': {e}")
