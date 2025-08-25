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
        if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', s):
            return False
        return base64.b64encode(base64.b64decode(s.encode('ascii'))).decode('ascii') == s
    except (Exception):
        return False

def decode_content(content: str) -> str:
    """
    محتوای ورودی را بررسی کرده و در صورتیکه Base64 باشد، آن را رمزگشایی می‌کند.
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if lines and all(' ' not in line for line in lines):
        potential_base64_blob = "".join(lines)
        if is_base64(potential_base64_blob):
            try:
                logging.info("محتوای Base64 تشخیص داده شد، در حال رمزگشایی...")
                decoded_bytes = base64.b64decode(potential_base64_blob)
                return decoded_bytes.decode('utf-8')
            except Exception as e:
                logging.error(f"خطا در رمزگشایی محتوای Base64: {e}")
                return content
    return "\n".join(lines)

def parse_nodes(decoded_content: str) -> List[str]:
    """
    تمام لینک‌های کانفیگ معتبر را از محتوای متنی استخراج می‌کند، با تمرکز بر IP:PORT برای HTTP/HTTPS.
    """
    nodes: Set[str] = set()

    # الگوی IP:PORT
    ip_port_pattern = r'\b(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})\b'
    
    # پیدا کردن تمام IP:PORT ها و ساخت لینک‌های http/https
    for proxy in re.findall(ip_port_pattern, decoded_content):
        nodes.add(f"http://{proxy}")
        nodes.add(f"https://{proxy}")

    # الگوی کلی برای سایر پروتکل‌ها
    other_protocol_pattern = re.compile(
        r'(?i)\b((?:vless|vmess|trojan|ss|ssr|tuic|hy2|hysteria2|hysteria|snell|anytls|mieru|juicity|ssh|wireguard|warp|socks4|socks5|mtproto)://[^\s<>"\'\\]+)',
    )
    nodes.update(re.findall(other_protocol_pattern, decoded_content))

    return sorted(list(nodes))

def categorize_nodes(nodes: List[str]) -> Dict[str, List[str]]:
    """
    لیستی از نودها را بر اساس پروتکل آن‌ها دسته‌بندی می‌کند.
    """
    categorized: Dict[str, List[str]] = {}
    
    protocol_aliases = {
        "hysteria2": "hy2"
    }
    
    for node in nodes:
        try:
            protocol = node.split('://', 1)[0].lower()
            canonical_protocol = protocol_aliases.get(protocol, protocol)
            
            if canonical_protocol not in categorized:
                categorized[canonical_protocol] = []
            categorized[canonical_protocol].append(node)
        except IndexError:
            logging.warning(f"نود با فرمت نامعتبر نادیده گرفته شد: {node}")
            continue
            
    # Split http into http and https based on the scheme
    http_nodes = categorized.pop("http", [])
    http_proxies = [node for node in http_nodes if node.startswith("http://")]
    https_proxies = [node for node in http_nodes if node.startswith("https://")]

    if http_proxies:
        categorized["http"] = http_proxies
    if https_proxies:
        categorized["https"] = https_proxies

    return categorized
