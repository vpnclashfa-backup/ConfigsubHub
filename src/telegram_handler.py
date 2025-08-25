import logging
import re
import html
import base64
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

from .config import REQUEST_HEADERS, TELEGRAM_POST_MAX_AGE_DAYS
from .parser import parse_nodes, is_base64

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

def extract_configs_from_message(message_div: BeautifulSoup) -> List[str]:
    """
    کانفیگ‌ها را با یک استراتژی چند لایه و جامع از یک پست استخراج می‌کند.
    """
    all_potential_strings = set()

    # لایه ۱: استخراج از تگ‌های <code> و <pre> (اولویت بالا)
    for tag in message_div.find_all(['code', 'pre']):
        all_potential_strings.add(tag.get_text())

    # لایه ۲: استخراج کل متن پست
    full_text = message_div.get_text(separator='\n')
    all_potential_strings.add(full_text)

    # لایه ۳: جستجوی کلمات Base64 در کل متن
    for word in re.split(r'[\s\n<>]+', full_text):
        if is_base64(word):
            try:
                decoded_word = base64.b64decode(word).decode('utf-8', errors='ignore')
                all_potential_strings.add(decoded_word)
            except Exception:
                continue

    # تجمیع تمام رشته‌های یافت شده
    combined_text = "\n".join(all_potential_strings)

    # لایه ۴: جستجوی مستقیم با Regex روی متن تجمیع شده
    pattern = re.compile(r'(vless|vmess|ss|ssr|trojan|hy2|hysteria2|tuic)://[^\s\'"<>]+')
    found_configs = pattern.findall(combined_text)

    # پاک‌سازی نهایی: unescape کردن کدهای HTML
    cleaned_configs = [html.unescape(config) for config in found_configs]
    
    return cleaned_configs

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
        return [], True

    soup = BeautifulSoup(html_content, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    
    if not messages:
        logging.warning(f"هشدار: هیچ پستی در صفحه '{channel_id}' یافت نشد. ممکن است کانال خصوصی باشد.")
        return [], True

    all_configs = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)
    
    for message in messages:
        time_tag = message.find_parent('div', class_='tgme_widget_message').find('time', class_='time')
        if not time_tag or not time_tag.has_attr('datetime'): continue
        try:
            post_date = datetime.fromisoformat(time_tag['datetime'])
            if post_date < cutoff_date:
                logging.info(f"رسیدن به پست‌های قدیمی در '{channel_id}'. بررسی این کانال تمام شد.")
                break
        except ValueError:
            continue
        
        # استخراج با روش جدید و جامع
        configs_in_post = extract_configs_from_message(message)
        if configs_in_post:
            all_configs.update(configs_in_post)

    if not all_configs:
        logging.warning(f"هیچ کانفیگی در پست‌های اخیر کانال '{channel_id}' یافت نشد.")
        return [], True

    # اعتبارسنجی نهایی
    final_valid_configs = parse_nodes("\n".join(all_configs))

    logging.info(f"===== پایان عملیات برای کانال {channel_id}. مجموعاً {len(final_valid_configs)} کانفیگ منحصر به فرد و معتبر یافت شد. =====")
    return final_valid_configs, True
