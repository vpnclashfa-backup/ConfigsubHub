import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

from .config import REQUEST_HEADERS, TELEGRAM_POST_MAX_AGE_DAYS
from .parser import parse_nodes

def normalize_channel_id(raw_id: str) -> Optional[str]:
    """شناسه کانال تلگرام را به فرمت استاندارد (فقط ID) تبدیل می‌کند."""
    raw_id = raw_id.strip()
    if not raw_id: return None
    if raw_id.startswith('@'): return raw_id[1:]
    if 't.me/' in raw_id:
        match = re.search(r't\.me/(?:s/)?([\w\d_]+)', raw_id)
        if match: return match.group(1)
    if re.match(r'^[\w\d_]+$', raw_id): return raw_id
    logging.warning(f"فرمت شناسه تلگرام نامعتبر است و نادیده گرفته شد: '{raw_id}'")
    return None

def extract_configs_from_raw_html(html_content: str) -> List[str]:
    """کانفیگ‌ها را با استفاده از Regex مستقیماً از کل محتوای HTML استخراج می‌کند."""
    # این الگو بهبود یافته تا از گرفتن کاراکترهای ناخواسته مثل ' یا " در انتهای لینک جلوگیری کند.
    pattern = re.compile(r'(vless|vmess|ss|ssr|trojan|hy2|hysteria2|tuic)://[^\s\'"<>]+')
    return pattern.findall(html_content)

async def scrape_channel(session: aiohttp.ClientSession, channel_id: str) -> Tuple[List[str], bool]:
    """
    پست‌های یک کانال تلگرام را به صورت آسنکرون اسکرپ کرده و کانفیگ‌ها را استخراج می‌کند.
    """
    url = f"https://t.me/s/{channel_id}"
    logging.info(f"===== شروع عملیات اسکرپ برای کانال: {channel_id} ({url}) =====")

    try:
        async with session.get(url, headers=REQUEST_HEADERS, timeout=20) as response:
            if response.status == 404:
                logging.error(f"کانال '{channel_id}' یافت نشد (404). این کانال از لیست حذف خواهد شد.")
                return [], False
            
            response.raise_for_status()
            html_content = await response.text()

    except aiohttp.ClientError as e:
        logging.error(f"خطای شبکه در دسترسی به کانال {channel_id}: {e}")
        return [], True
    except Exception as e:
        logging.error(f"یک خطای پیش‌بینی نشده هنگام اسکرپ کانال {channel_id} رخ داد: {e}")
        return [], True

    # --- استراتژی جدید و اصلی: استخراج مستقیم و سپس اعتبارسنجی ---
    logging.info(f"روش استخراج برای '{channel_id}': جستجوی مستقیم در کل محتوای HTML...")
    
    # مرحله 1: استخراج تمام کانفیگ‌های احتمالی از HTML خام
    potential_configs = extract_configs_from_raw_html(html_content)
    
    if not potential_configs:
        logging.warning(f"هشدار: هیچ کانفیگ احتمالی در صفحه '{channel_id}' یافت نشد.")
        return [], True # کانال وجود دارد اما کانفیگی یافت نشد

    logging.info(f"{len(potential_configs)} کانفیگ احتمالی با جستجوی مستقیم در '{channel_id}' یافت شد.")

    # مرحله 2: (اختیاری اما مفید) بررسی اینکه آیا کانال اخیراً آپدیت شده یا نه
    soup = BeautifulSoup(html_content, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    is_channel_updated_recently = False
    if messages:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)
        for message in messages:
            time_tag = message.find_parent('div', class_='tgme_widget_message').find('time', class_='time')
            if time_tag and time_tag.has_attr('datetime'):
                try:
                    post_date = datetime.fromisoformat(time_tag['datetime'])
                    if post_date >= cutoff_date:
                        is_channel_updated_recently = True
                        logging.info(f"کانال '{channel_id}' حاوی پست‌های جدید است. پردازش ادامه می‌یابد.")
                        break 
                except ValueError:
                    continue
        if not is_channel_updated_recently:
            logging.info(f"کانال '{channel_id}' در {TELEGRAM_POST_MAX_AGE_DAYS} روز اخیر پستی نداشته. از کانفیگ‌های آن صرف‌نظر می‌شود.")
            # return [], True # اگر می‌خواهید کانفیگ کانال‌های قدیمی را نگیرید، این خط را فعال کنید
    
    # مرحله 3: اعتبارسنجی نهایی تمام کانفیگ‌های استخراج شده
    final_valid_configs = parse_nodes("\n".join(potential_configs))

    logging.info(f"===== پایان عملیات برای کانال {channel_id}. مجموعاً {len(final_valid_configs)} کانفیگ منحصر به فرد و معتبر یافت شد. =====")
    return final_valid_configs, True
