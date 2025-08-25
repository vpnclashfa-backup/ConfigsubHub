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
    تمام لینک‌های کانفیگ معتبر را از محتوای متنی استخراج می‌کند.
    برای HTTP/HTTPS، فقط فرمت protocol://IP:PORT را می‌پذیرد.
    """
    nodes: Set[str] = set()

    # 1. الگوی دقیق برای HTTP/HTTPS Proxies با فرمت IP:PORT
    # https? matches http or https. The rest matches a valid IPv4 and port.
    http_proxy_pattern = re.compile(
        r'\b(https?://\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})\b',
        re.IGNORECASE
    )
    nodes.update(http_proxy_pattern.findall(decoded_content))

    # 2. الگوی کلی برای سایر پروتکل‌ها
    other_protocols = [
        "vless", "vmess", "trojan", "ss", "ssr", "tuic", "hy2", "hysteria2",
        "hysteria", "snell", "anytls", "mieru", "juicity", "ssh",
        "wireguard", "warp", "socks4", "socks5", "mtproto"
    ]
    other_protocol_pattern = re.compile(
        r'(?i)\b((?:' + '|'.join(other_protocols) + r')://[^\s<>"\'\\]+)'
    )
    nodes.update(other_protocol_pattern.findall(decoded_content))

    return sorted(list(nodes))

def categorize_nodes(nodes: List[str]) -> Dict[str, List[str]]:
    """
    لیستی از نودها را بر اساس پروتکل آن‌ها دسته‌بندی می‌کند (HTTP و HTTPS جدا هستند).
    """
    categorized: Dict[str, List[str]] = {}
    
    protocol_aliases = {
        "hysteria2": "hy2",
        # No aliasing for http/https, they will be categorized separately
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
            
    return categorized
