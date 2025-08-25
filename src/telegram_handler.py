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
    pattern = re.compile(r'(vless|vmess|ss|ssr|trojan|hy2|hysteria2|tuic)://[^\s\'"<]+')
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
        return [], True # ممکن است مشکل موقتی باشد، کانال را حذف نکن
    except Exception as e:
        logging.error(f"یک خطای پیش‌بینی نشده هنگام اسکرپ کانال {channel_id} رخ داد: {e}")
        return [], True


    all_configs = set()
    
    # استخراج مستقیم از HTML خام
    logging.info(f"روش استخراج برای '{channel_id}': جستجوی مستقیم کانفیگ‌ها در کل محتوای HTML...")
    direct_configs = extract_configs_from_raw_html(html_content)
    if direct_configs:
        logging.info(f"{len(direct_configs)} کانفیگ احتمالی با جستجوی مستقیم در '{channel_id}' یافت شد.")
        all_configs.update(direct_configs)

    # فیلتر زمانی پست‌ها (این بخش همچنان مفید است تا کانفیگ‌های خیلی قدیمی را استخراج نکنیم)
    soup = BeautifulSoup(html_content, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    
    if not messages and not direct_configs:
        logging.warning(f"هشدار: هیچ پستی یا کانفیگی در صفحه '{channel_id}' یافت نشد.")
        return [], True

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)
    
    valid_html_configs = set()
    for config in direct_configs:
        # یک بررسی ساده برای اینکه بفهمیم کانفیگ در کدام بخش صفحه بوده
        # اگر در هیچ پستی نبود، فرض می‌کنیم معتبر است
        # اگر در پستی بود، تاریخ آن را چک می‌کنیم
        is_in_recent_post = False
        for message in messages:
            if config in message.get_text():
                time_tag = message.find_parent('div', class_='tgme_widget_message').find('time', class_='time')
                if time_tag and time_tag.has_attr('datetime'):
                    try:
                        post_date = datetime.fromisoformat(time_tag['datetime'])
                        if post_date >= cutoff_date:
                            is_in_recent_post = True
                            break
                    except ValueError:
                        pass
        
        # اگر کانفیگ در هیچ پستی یافت نشد یا در پست جدیدی بود، آن را نگه دار
        if is_in_recent_post or not messages:
             valid_html_configs.add(config)

    final_valid_configs = parse_nodes("\n".join(valid_html_configs))

    logging.info(f"===== پایان عملیات برای کانال {channel_id}. مجموعاً {len(final_valid_configs)} کانفیگ منحصر به فرد و معتبر یافت شد. =====")
    return final_valid_configs, True
