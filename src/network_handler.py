import asyncio
import logging
from typing import List, Tuple

import aiohttp

# وارد کردن تنظیمات از config.py
from .config import REQUEST_HEADERS, REQUEST_TIMEOUT

async def fetch_sub(session: aiohttp.ClientSession, name: str, url: str) -> Tuple[str, str]:
    """
    محتوای یک لینک اشتراک را به صورت آسنکرون دانلود می‌کند.

    Args:
        session: یک aiohttp.ClientSession فعال.
        name: نام سفارشی لینک.
        url: آدرس URL لینک برای دانلود.

    Returns:
        یک تاپل شامل (نام، محتوای دانلود شده یا رشته خالی در صورت خطا).
    """
    try:
        logging.info(f"در حال ارسال درخواست به: {name} ({url})")
        async with session.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT) as response:
            # بررسی موفقیت آمیز بودن درخواست
            if response.status == 200:
                content = await response.text()
                logging.info(f"محتوای '{name}' با موفقیت دریافت شد.")
                return name, content
            else:
                logging.error(f"خطا در دریافت محتوای '{name}'. کد وضعیت: {response.status}")
                return name, ""
    except asyncio.TimeoutError:
        logging.error(f"درخواست برای '{name}' به دلیل پایان زمان مهلت (Timeout) لغو شد.")
        return name, ""
    except aiohttp.ClientError as e:
        logging.error(f"خطای شبکه هنگام درخواست برای '{name}': {e}")
        return name, ""
    except Exception as e:
        logging.error(f"یک خطای پیش‌بینی نشده برای '{name}' رخ داد: {e}")
        return name, ""


async def fetch_all_subs(session: aiohttp.ClientSession, links: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    محتوای تمام لینک‌ها را به صورت موازی و آسنکرون با استفاده از سشن مشترک دانلود می‌کند.

    Args:
        session: یک aiohttp.ClientSession فعال و مشترک.
        links: لیستی از تاپل‌ها که هر کدام شامل (نام، لینک) است.

    Returns:
        لیستی از نتایج دانلود شده به صورت تاپل (نام، محتوا).
    """
    # ایجاد لیستی از تسک‌ها برای اجرای همزمان
    tasks = [fetch_sub(session, name, url) for name, url in links]
    
    # اجرای همه تسک‌ها و جمع‌آوری نتایج
    results = await asyncio.gather(*tasks)
    
    return results
