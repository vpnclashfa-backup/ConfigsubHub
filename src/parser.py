import base64
import logging
import re
from typing import List, Dict, Set

def is_base64(s: str) -> bool:
    """
    بررسی می‌کند که آیا یک رشته Base64 معتبر است یا خیر.
    """
    if not s or not isinstance(s, str) or len(s.strip()) == 0:
        return False
    try:
        # Check for valid Base64 characters and padding
        if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', s):
            return False
        return base64.b64encode(base64.b64decode(s.encode('ascii'))).decode('ascii') == s
    except (Exception):
        return False

def decode_content(content: str) -> str:
    """
    محتوای ورودی را بررسی کرده و در صورتیکه Base64 باشد، آن را رمزگشایی می‌کند.
    """
    # Remove empty lines and strip whitespace from each line
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    
    # Heuristic to detect if the whole content is likely a single base64 blob
    # It should not contain spaces and be composed of a few long lines
    if lines and all(' ' not in line for line in lines):
        potential_base64_blob = "".join(lines)
        if is_base64(potential_base64_blob):
            try:
                logging.info("محتوای Base64 تشخیص داده شد، در حال رمزگشایی...")
                decoded_bytes = base64.b64decode(potential_base64_blob)
                return decoded_bytes.decode('utf-8')
            except Exception as e:
                logging.error(f"خطا در رمزگشایی محتوای Base64: {e}")
                # Return original content on failure
                return content
    # If not detected as a single blob, return the original (but cleaned) content
    return "\n".join(lines)

def parse_nodes(decoded_content: str) -> List[str]:
    """
    تمام لینک‌های کانفیگ معتبر را از محتوای متنی با استفاده از یک Regex جامع استخراج می‌کند.
    این تابع قادر است لینک‌ها را از هر کجای متن پیدا کند.
    """
    # لیست تمام پروتکل‌های پشتیبانی شده
    protocols = [
        "vless", "vmess", "trojan", "ss", "ssr", "tuic", "hy2", "hysteria2",
        "hysteria", "snell", "anytls", "mieru", "juicity", "ssh",
        "wireguard", "warp", "socks4", "socks5", "mtproto", "http", "https"
    ]
    
    # ساخت یک الگوی Regex جامع برای یافتن تمام لینک‌ها در یک حرکت
    # (?i) for case-insensitivity, (?:...) for non-capturing group
    # [^\s<>"']+ looks for any character except whitespace or common delimiters
    protocol_pattern = r'(?i)\b((?:' + '|'.join(protocols) + r')://[^\s<>"\'\\]+)'
    
    found_nodes: Set[str] = set(re.findall(protocol_pattern, decoded_content))
    
    # اضافه کردن پراکسی‌های ساده HTTP(S) با فرمت IP:PORT
    # این الگو به دنبال IP:PORT می‌گردد که بخشی از یک لینک دیگر نباشد.
    ip_port_pattern = r'\b(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})\b'
    potential_proxies = re.findall(ip_port_pattern, decoded_content)
    
    for proxy in potential_proxies:
        # اطمینان از اینکه این IP:PORT قبلاً در یک لینک کامل‌تر یافت نشده است
        if not any(proxy in node for node in found_nodes):
            # برای سازگاری، آنها را به فرمت http تبدیل می‌کنیم
            found_nodes.add(f"http://{proxy}")

    return sorted(list(found_nodes))

def categorize_nodes(nodes: List[str]) -> Dict[str, List[str]]:
    """
    لیستی از نودها را بر اساس پروتکل آن‌ها دسته‌بندی می‌کند و نام‌های مستعار را نرمال‌سازی می‌کند.
    """
    categorized: Dict[str, List[str]] = {}
    
    # نگاشت نام‌های مستعار به نام اصلی پروتکل
    protocol_aliases = {
        "hysteria2": "hy2",
        "https": "http", # https and http proxies are often treated the same
    }
    
    for node in nodes:
        try:
            protocol = node.split('://', 1)[0].lower()
            
            # استفاده از نام اصلی پروتکل در صورت وجود در لیست نام‌های مستعار
            canonical_protocol = protocol_aliases.get(protocol, protocol)
            
            if canonical_protocol not in categorized:
                categorized[canonical_protocol] = []
            categorized[canonical_protocol].append(node)
        except IndexError:
            # اگر لینکی فرمت protocol:// را نداشته باشد، نادیده گرفته می‌شود
            logging.warning(f"نود با فرمت نامعتبر نادیده گرفته شد: {node}")
            continue
            
    return categorized
