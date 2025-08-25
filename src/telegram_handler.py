import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, NavigableString

from .config import REQUEST_HEADERS, TELEGRAM_POST_MAX_AGE_DAYS
from .parser import parse_nodes


def normalize_channel_id(raw_id: str) -> Optional[str]:
    """
    شناسه کانال تلگرام را به فرمت استاندارد (فقط ID) تبدیل می‌کند.
    """
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


def extract_text_from_message(message_div: BeautifulSoup) -> str:
    """
    متن را از تمام بخش‌های یک پست تلگرام، شامل متن عادی، کد، اسپویلر و ... استخراج می‌کند.
    """
    for br in message_div.find_all('br'):
        br.replace_with('\n')
    return message_div.get_text(separator=' ')


def find_and_split_configs(text: str) -> List[str]:
    """
    کانفیگ‌های به‌هم‌چسبیده را پیدا و از هم جدا می‌کند.
    """
    pattern = re.compile(r'(vless|vmess|trojan|ss|ssr|tuic|hy2|hysteria2|hysteria|snell|anytls|mieru|juicity|ssh|wireguard|warp|socks4|socks5|mtproto|http|https):\/\/')
    
    found_configs = []
    indices = [m.start() for m in pattern.finditer(text)]
    
    if not indices:
        return []

    for i in range(len(indices)):
        start_pos = indices[i]
        # اصلاح سینتکس: استفاده صحیح از if/else کوتاه‌شده
        end_pos = indices[i + 1] if i + 1 < len(indices) else len(text)
        config_str = text[start_pos:end_pos].strip()
        found_configs.append(config_str)
        
    return parse_nodes("\n".join(found_configs))


def scrape_channel(channel_id: str) -> Tuple[List[str], bool]:
    """
    پست‌های یک کانال تلگرام را اسکرپ کرده و کانفیگ‌های معتبر را استخراج می‌کند.
    یک تاپل (لیست کانفیگ‌ها، وضعیت اعتبار کانال) برمی‌گرداند.
    """
    url = f"https://t.me/s/{channel_id}"
    logging.info(f"===== شروع عملیات اسکرپ برای کانال: {channel_id} ({url}) =====")

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logging.error(f"کانال '{channel_id}' یافت نشد (خطای 404). این کانال از لیست حذف خواهد شد.")
            return [], False
        logging.error(f"خطای HTTP در دسترسی به کانال {channel_id}: {e}")
        return [], True
    except requests.RequestException as e:
        logging.error(f"خطا در دریافت اطلاعات از کانال {channel_id}. عملیات برای این کانال متوقف شد. جزئیات: {e}")
        return [], True

    soup = BeautifulSoup(response.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    
    if not messages:
        logging.warning(f"هیچ پستی در صفحه کانال '{channel_id}' یافت نشد. ممکن است کانال خصوصی باشد یا پستی نداشته باشد.")
        return [], True

    all_configs = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)
    post_counter = 0

    for message in messages:
        post_counter += 1
        post_link_tag = message.find_parent('div', class_='tgme_widget_message').find('a', class_='tgme_widget_message_date')
        post_link = post_link_tag['href'] if post_link_tag else "نا مشخص"
        
        logging.info(f"--- بررسی پست شماره {post_counter} از کانال '{channel_id}' ({post_link}) ---")

        time_tag = message.find_parent('div', class_='tgme_widget_message').find('time', class_='time')
        if not time_tag or not time_tag.has_attr('datetime'):
            logging.warning("تگ زمان برای این پست یافت نشد. از این پست صرف‌نظر می‌شود.")
            continue
        
        try:
            post_date = datetime.fromisoformat(time_tag['datetime'])
        except ValueError:
            logging.warning(f"فرمت تاریخ پست نامعتبر است: '{time_tag['datetime']}'. از این پست صرف‌نظر می‌شود.")
            continue

        if post_date < cutoff_date:
            logging.info(f"پست قدیمی است (تاریخ: {post_date.strftime('%Y-%m-%d')}). عملیات اسکرپ برای کانال '{channel_id}' به پایان رسید.")
            break
        
        post_text = extract_text_from_message(message)
        if not post_text.strip():
            logging.info("این پست فاقد متن است (ممکن است فقط عکس یا ویدیو باشد).")
            continue

        logging.debug(f"متن استخراج شده از پست: \n---\n{post_text[:500].strip()}...\n---")
        configs_in_post = find_and_split_configs(post_text)
        
        if configs_in_post:
            newly_added_count = len(set(configs_in_post) - all_configs)
            all_configs.update(configs_in_post)
            logging.info(f"نتیجه: {len(configs_in_post)} کانفیگ در این پست پیدا شد. ({newly_added_count} کانفیگ جدید به لیست اضافه شد).")
        else:
            logging.info("نتیجه: هیچ کانفیگ معتبری در این پست یافت نشد.")
            
    logging.info(f"===== پایان عملیات اسکرپ برای کانال {channel_id}. مجموعاً {len(all_configs)} کانفیگ منحصر به فرد یافت شد. =====")
    return list(all_configs), True
