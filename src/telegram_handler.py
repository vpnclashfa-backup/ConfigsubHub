import logging
import re
import html
import base64
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Set

import aiohttp
from bs4 import BeautifulSoup, Tag

from .config import REQUEST_HEADERS, TELEGRAM_POST_MAX_AGE_DAYS
from .parser import parse_nodes, is_base64

def normalize_channel_id(raw_id: str) -> Optional[str]:
    """شناسه کانال تلگرام را به فرمت استاندارد (فقط ID) تبدیل می‌کند."""
    raw_id = raw_id.strip()
    if not raw_id:
        return None
    if raw_id.startswith('@'):
        return raw_id[1:]
    if 't.me/' in raw_id:
        # Handles both t.me/channel and t.me/s/channel formats
        match = re.search(r't\.me/(?:s/)?([\w\d_]+)', raw_id)
        if match:
            return match.group(1)
    # Check if it's a plain channel ID
    if re.match(r'^[\w\d_]+$', raw_id):
        return raw_id
    logging.warning(f"فرمت شناسه تلگرام نامعتبر است و نادیده گرفته شد: '{raw_id}'")
    return None

def extract_configs_from_message(message_div: Tag) -> List[str]:
    """
    کانفیگ‌ها را با یک استراتژی چند لایه و جامع از یک پست استخراج کرده و اعتبارسنجی می‌کند.
    این تابع تمام رشته‌های بالقوه را جمع‌آوری کرده و برای اعتبارسنجی نهایی به parser می‌فرستد.
    """
    potential_strings: Set[str] = set()

    # --- لایه ۱: استخراج از تگ‌های <code> و <pre> (اولویت بالا) ---
    for tag in message_div.find_all(['code', 'pre']):
        potential_strings.add(tag.get_text(separator='\n'))

    # --- لایه ۲: استخراج کل متن پست برای یافتن لینک‌های مستقیم و Base64 ---
    full_text = message_div.get_text(separator='\n')
    
    # افزودن کل متن برای پیدا کردن لینک‌هایی که در تگ خاصی نیستند
    potential_strings.add(full_text)

    # --- لایه ۳: جستجوی هوشمند کلمات Base64 در کل متن ---
    # کلمات را بر اساس فاصله، خط جدید یا تگ‌های HTML جدا می‌کنیم
    for word in re.split(r'[\s\n<>]+', full_text):
        word = word.strip()
        if len(word) > 20 and is_base64(word):  # حداقل طول برای کاهش خطای تشخیص
            try:
                decoded_word = base64.b64decode(word).decode('utf-8', errors='ignore')
                potential_strings.add(decoded_word)
                logging.info("یک رشته Base64 در متن پیام شناسایی و رمزگشایی شد.")
            except Exception:
                continue

    # --- تجمیع و اعتبارسنجی نهایی ---
    # تمام رشته‌های یافت شده را در یک متن بزرگ ترکیب می‌کنیم
    combined_text = "\n".join(filter(None, potential_strings))
    
    # برای پاک‌سازی نهایی، کدهای HTML باقیمانده را unescape می‌کنیم
    cleaned_text = html.unescape(combined_text)

    # تمام متن جمع‌آوری شده را برای اعتبارسنجی به ماژول parser ارسال می‌کنیم
    return parse_nodes(cleaned_text)

async def scrape_channel(session: aiohttp.ClientSession, channel_id: str) -> Tuple[List[str], bool]:
    """
    پست‌های یک کانال تلگرام را به صورت آسنکرون اسکرپ کرده و کانفیگ‌ها را استخراج می‌کند.
    """
    url = f"https://t.me/s/{channel_id}"
    logging.info(f"===== شروع عملیات اسکرپ برای کانال: {channel_id} ({url}) =====")

    try:
        async with session.get(url, headers=REQUEST_HEADERS, timeout=30) as response:
            if response.status == 404:
                logging.error(f"کانال '{channel_id}' یافت نشد (404). این کانال از لیست حذف خواهد شد.")
                return [], False
            response.raise_for_status()
            html_content = await response.text()
    except Exception as e:
        logging.error(f"خطا در دسترسی به کانال {channel_id}: {e}")
        # کانال معتبر است اما در دسترس نیست، پس True برمی‌گردانیم تا حذف نشود
        return [], True

    soup = BeautifulSoup(html_content, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    
    if not messages:
        logging.warning(f"هشدار: هیچ پستی در صفحه '{channel_id}' یافت نشد. ممکن است کانال خصوصی یا خالی باشد.")
        return [], True

    all_configs: Set[str] = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)
    
    for message in messages:
        # یافتن تگ والد برای دسترسی به تگ زمان
        message_container = message.find_parent('div', class_='tgme_widget_message')
        if not message_container:
            continue
            
        time_tag = message_container.find('time', class_='time')
        if not time_tag or not time_tag.has_attr('datetime'):
            continue
            
        try:
            post_date = datetime.fromisoformat(time_tag['datetime'])
            if post_date < cutoff_date:
                logging.info(f"رسیدن به پست‌های قدیمی‌تر از {TELEGRAM_POST_MAX_AGE_DAYS} روز در '{channel_id}'. بررسی این کانال متوقف شد.")
                break
        except (ValueError, TypeError):
            continue
        
        # استخراج کانفیگ‌ها با روش جدید و جامع
        configs_in_post = extract_configs_from_message(message)
        if configs_in_post:
            all_configs.update(configs_in_post)

    if not all_configs:
        logging.warning(f"هیچ کانفیگ معتبری در پست‌های اخیر کانال '{channel_id}' یافت نشد.")
        return [], True

    final_valid_configs = sorted(list(all_configs))
    logging.info(f"===== پایان عملیات برای کانال {channel_id}. مجموعاً {len(final_valid_configs)} کانفیگ منحصر به فرد و معتبر یافت شد. =====")
    return final_valid_configs, True
