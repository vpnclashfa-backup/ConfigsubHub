import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from bs4 import BeautifulSoup, NavigableString

from .config import REQUEST_HEADERS, TELEGRAM_POST_MAX_AGE_DAYS
from .parser import parse_nodes


def normalize_channel_id(raw_id: str) -> Optional[str]:
    """
    شناسه کانال تلگرام را به فرمت استاندارد (فقط ID) تبدیل می‌کند.
    مثال‌ها:
    - vpnclashfa -> vpnclashfa
    - @vpnclashfa -> vpnclashfa
    - https://t.me/vpnclashfa -> vpnclashfa
    - https://t.me/s/v2rayng_fa2 -> v2rayng_fa2
    """
    raw_id = raw_id.strip()
    if not raw_id:
        return None

    # حذف @ از ابتدا
    if raw_id.startswith('@'):
        return raw_id[1:]

    # استخراج از URL
    if 't.me/' in raw_id:
        # مدیریت حالت /s/
        match = re.search(r't\.me/(?:s/)?([\w\d_]+)', raw_id)
        if match:
            return match.group(1)

    # اگر فقط ID خالص بود
    if re.match(r'^[\w\d_]+$', raw_id):
        return raw_id

    logging.warning(f"فرمت شناسه تلگرام نامعتبر است: {raw_id}")
    return None


def extract_text_from_message(message_div: BeautifulSoup) -> str:
    """
    متن را از تمام بخش‌های یک پست تلگرام، شامل متن عادی، کد، اسپویلر و ... استخراج می‌کند.
    """
    # تمام تگ‌های <br> را با یک خط جدید جایگزین می‌کنیم تا ساختار خطوط حفظ شود.
    for br in message_div.find_all('br'):
        br.replace_with('\n')

    # متن را از تمام المنت‌ها استخراج می‌کنیم (شامل متن داخل <code>, <b>, <span> و...)
    return message_div.get_text(separator=' ')


def find_and_split_configs(text: str) -> List[str]:
    """
    کانفیگ‌های به‌هم‌چسبیده را پیدا و از هم جدا می‌کند.
    مثال: "some text vless://...vmess://... other text" -> ["vless://...", "vmess://..."]
    """
    # Regex برای پیدا کردن تمام پروتکل‌های شناخته شده
    # این الگو هر پروتکلی را به عنوان نقطه شروع یک کانفیگ جدید در نظر می‌گیرد.
    pattern = re.compile(r'(vless|vmess|trojan|ss|ssr|tuic|hy2|hysteria2|hysteria|snell|anytls|mieru|juicity|ssh|wireguard|warp|socks4|socks5|mtproto|http|https):\/\/')
    
    found_configs = []
    
    # پیدا کردن تمام نقاط شروع کانفیگ‌ها
    indices = [m.start() for m in pattern.finditer(text)]
    
    if not indices:
        return []

    # جدا کردن کانفیگ‌ها بر اساس نقاط شروع
    for i in range(len(indices)):
        start_pos = indices[i]
        # نقطه پایان، شروع کانفیگ بعدی یا انتهای رشته است
        end_pos = indices[i + 1] if i + 1 < len(indices) else len(text)
        
        config_str = text[start_pos:end_pos].strip()
        found_configs.append(config_str)
        
    # استفاده مجدد از parse_nodes برای اطمینان از اعتبار هر کانفیگ جدا شده
    return parse_nodes("\n".join(found_configs))


def scrape_channel(channel_id: str) -> List[str]:
    """
    پست‌های یک کانال تلگرام را اسکرپ کرده و کانفیگ‌های معتبر را استخراج می‌کند.
    """
    url = f"https://t.me/s/{channel_id}"
    logging.info(f"در حال اسکرپ کردن کانال تلگرام: {url}")

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"خطا در دریافت اطلاعات از کانال {channel_id}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_text')
    
    all_configs = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_POST_MAX_AGE_DAYS)

    for message in messages:
        # استخراج تاریخ پست
        time_tag = message.find_parent('div', class_='tgme_widget_message').find('time', class_='time')
        if not time_tag or not time_tag.has_attr('datetime'):
            continue
        
        try:
            post_date = datetime.fromisoformat(time_tag['datetime'])
        except ValueError:
            logging.warning("فرمت تاریخ پست تلگرام قابل شناسایی نیست.")
            continue

        # بررسی اینکه آیا پست در محدوده زمانی مجاز است یا خیر
        if post_date < cutoff_date:
            # از آنجایی که پست‌ها از جدید به قدیم هستند، می‌توانیم حلقه را متوقف کنیم
            logging.info(f"رسیدن به پست‌های قدیمی‌تر از {TELEGRAM_POST_MAX_AGE_DAYS} روز. توقف اسکرپ برای کانال {channel_id}.")
            break
        
        # استخراج متن کامل پست با در نظر گرفتن تمام تگ‌ها
        post_text = extract_text_from_message(message)
        
        # پیدا کردن کانفیگ‌های تکی و به‌هم‌چسبیده
        configs_in_post = find_and_split_configs(post_text)
        
        for config in configs_in_post:
            all_configs.add(config)
            
    logging.info(f"تعداد {len(all_configs)} کانفیگ منحصر به فرد از کانال {channel_id} استخراج شد.")
    return list(all_configs)
