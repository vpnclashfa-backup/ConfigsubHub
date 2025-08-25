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
from .log_handler import save_channel_error_log

def normalize_channel_id(raw_id: str) -> Optional[str]:
    """شناسه کانال تلگرام را به فرمت استاندارد (فقط ID) تبدیل می‌کند."""
    raw_id = raw_id.strip()
    if not raw_id:
        return None
    if raw_id.startswith('@'):
        return raw_id[1:]
    if 't.me/' in raw_id:
        match = re.search(r't\.me/(?:s/)?([\w\d_]+)', raw_id)
        if match:
            return match.group(1)
    if re.match(r'^[\w\d_]+$', raw_id):
        return raw_id
    logging.warning(f"فرمت شناسه تلگرام نامعتبر است و نادیده گرفته شد: '{raw_id}'")
    return None

def extract_configs_from_message(message_div: Tag) -> List[str]:
    """
    کانفیگ‌ها را با یک استراتژی چند لایه از یک پست استخراج و اعتبارسنجی می‌کند.
    """
    potential_strings: Set[str] = set()

    for tag in message_div.find_all(['code', 'pre']):
        potential_strings.add(tag.get_text(separator='\n'))

    full_text = message_div.get_text(separator='\n')
    potential_strings.add(full_text)

    for word in re.split(r'[\s\n<>]+', full_text):
        word = word.strip()
        if len(word) > 20 and is_base64(word):
            try:
                decoded_word = base64.b64decode(word).decode('utf-8', errors='ignore')
                potential_strings.add(decoded_word)
                logging.info("یک رشته Base64 در متن پیام شناسایی و رمزگشایی شد.")
            except Exception:
                continue

    combined_text = "\n".join(filter(None, potential_strings))
    cleaned_text = html.unescape(combined_text)
    return parse_nodes(cleaned_text)

async def scrape_channel(session: aiohttp.ClientSession, channel_id: str) -> Tuple[List[str], bool]:
    """
    پست‌های یک کانال تلگرام را اسکرپ کرده و کانفیگ‌ها را استخراج می‌کند.
    در صورت عدم موفقیت، یک لاگ خطا ذخیره می‌کند.
    """
    url = f"https://t.me/s/{channel_id}"
    logging.info(f"===== شروع عملیات اسکرپ برای کانال: {channel_id} ({url}) =====")
    html_content = ""
    try:
        async with session.get(url, headers=REQUEST_HEADERS, timeout=30) as response:
            if response.status == 404:
                logging.error(f"کانال '{channel_id}' یافت نشد (404).")
                await save_channel_error_log(channel_id, "کانال یافت نشد (404 Not Found).", [])
                return [], False
            response.raise_for_status()
            html_content = await response.text()
    except Exception as e:
        logging.error(f"خطا در دسترسی به کانال {channel_id}: {e}")
        await save_channel_error_log(channel_id, f"خطا در دسترسی به کانال: {e}", [])
        return [], True

    soup = BeautifulSoup(html_content, 'html.parser')
    message_containers = soup.find_all('div', class_='tgme_widget_message')
    
    if not message_containers:
        reason = "هیچ پستی در صفحه یافت نشد. ممکن است کانال خصوصی، خالی یا ساختار آن تغییر کرده باشد."
        logging.warning(f"هشدار: {reason} ({channel_id})")
        # Dump the entire body for analysis if no messages are found
        body_content = [soup.body] if soup.body else []
        await save_channel_error_log(channel_id, reason, body_content)
        return [], True

    all_configs: Set[str] = set()
    scanned_messages: List[Tag] = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)
    
    for container in message_containers:
        time_tag = container.find('time', class_='time')
        if not time_tag or not time_tag.has_attr('datetime'):
            continue
        try:
            post_date = datetime.fromisoformat(time_tag['datetime'])
            if post_date < cutoff_date:
                logging.info(f"رسیدن به پست‌های قدیمی‌تر از {TELEGRAM_POST_MAX_AGE_DAYS} روز در '{channel_id}'.")
                break
            
            scanned_messages.append(container) # Add message to the list of scanned messages
            
            message_text_div = container.find('div', class_='tgme_widget_message_text')
            if message_text_div:
                configs_in_post = extract_configs_from_message(message_text_div)
                if configs_in_post:
                    all_configs.update(configs_in_post)
        except (ValueError, TypeError):
            continue

    if not all_configs:
        reason = "هیچ کانفیگ معتبری در پست‌های اخیر یافت نشد."
        logging.warning(f"{reason} ({channel_id})")
        await save_channel_error_log(channel_id, reason, scanned_messages)
        return [], True

    final_valid_configs = sorted(list(all_configs))
    logging.info(f"===== پایان عملیات برای کانال {channel_id}. مجموعاً {len(final_valid_configs)} کانفیگ معتبر یافت شد. =====")
    return final_valid_configs, True
