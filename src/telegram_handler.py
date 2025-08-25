import logging
import re
import html
import base64
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Set

from playwright.async_api import Browser, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup, Tag

from .config import TELEGRAM_POST_MAX_AGE_DAYS
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
    """کانفیگ‌ها را با یک استراتژی چند لایه از یک پست استخراج و اعتبارسنجی می‌کند."""
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
            except Exception:
                continue

    combined_text = "\n".join(filter(None, potential_strings))
    cleaned_text = html.unescape(combined_text)
    return parse_nodes(cleaned_text)

async def scrape_channel(browser: Browser, channel_id: str) -> Tuple[List[str], bool]:
    """
    پست‌های یک کانال تلگرام را با استفاده از Playwright (شبیه‌ساز مرورگر) اسکرپ می‌کند.
    """
    url = f"https://t.me/s/{channel_id}"
    logging.info(f"===== [Playwright] شروع عملیات برای کانال: {channel_id} =====")
    
    context = None
    page = None
    try:
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = await context.new_page()
        
        await page.goto(url, timeout=45000)
        
        # منتظر می‌مانیم تا حداقل یک کانتینر پیام بارگذاری شود
        # این مهم‌ترین بخش برای دور زدن صفحات پیش‌نمایش است
        await page.wait_for_selector('div.tgme_widget_message', timeout=15000)

        html_content = await page.content()

    except PlaywrightTimeoutError:
        reason = "صفحه در زمان مقرر بارگذاری نشد یا هیچ پستی یافت نشد (Timeout)."
        logging.error(f"{reason} ({channel_id})")
        # ممکن است صفحه پیش‌نمایش بارگذاری شده باشد، پس محتوای آن را ذخیره می‌کنیم
        content_for_log = ""
        if page:
            content_for_log = await page.content()
        soup_for_log = BeautifulSoup(content_for_log, 'html.parser')
        await save_channel_error_log(channel_id, reason, [soup_for_log.body] if soup_for_log.body else [])
        return [], True # ممکن است مشکل موقتی باشد، پس کانال را حذف نمی‌کنیم
    except Exception as e:
        reason = f"خطای Playwright هنگام دسترسی به کانال: {e}"
        logging.error(f"{reason} ({channel_id})")
        await save_channel_error_log(channel_id, reason, [])
        return [], True
    finally:
        if page: await page.close()
        if context: await context.close()

    soup = BeautifulSoup(html_content, 'html.parser')
    # توجه: ما از 'tgme_widget_message' استفاده می‌کنیم چون والد 'tgme_widget_message_text' است
    # و شامل تگ زمان (time tag) نیز می‌شود.
    message_containers = soup.find_all('div', class_='tgme_widget_message')
    
    if not message_containers:
        # این حالت بعید است به دلیل wait_for_selector، اما برای اطمینان بررسی می‌شود
        reason = "هیچ پستی در محتوای نهایی صفحه یافت نشد."
        logging.warning(f"هشدار: {reason} ({channel_id})")
        await save_channel_error_log(channel_id, reason, [soup.body] if soup.body else [])
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
                logging.info(f"رسیدن به پست‌های قدیمی در '{channel_id}'.")
                break
            
            scanned_messages.append(container)
            
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
    logging.info(f"===== [Playwright] پایان عملیات برای کانال {channel_id}. {len(final_valid_configs)} کانفیگ یافت شد. =====")
    return final_valid_configs, True
