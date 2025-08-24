import base64
import logging
import re
from typing import List, Dict

def is_base64(s: str) -> bool:
    """
    بررسی می‌کند که آیا یک رشته Base64 معتبر است یا خیر.
    """
    try:
        return base64.b64encode(base64.b64decode(s.encode('ascii'))).decode('ascii') == s
    except (Exception):
        return False

def decode_content(content: str) -> str:
    """
    محتوای ورودی را بررسی کرده و در صورتیکه Base64 باشد، آن را رمزگشایی می‌کند.
    """
    cleaned_content = "\n".join(filter(None, (line.strip() for line in content.splitlines())))
    
    if ' ' not in cleaned_content and is_base64(cleaned_content):
        try:
            logging.info("محتوای Base64 تشخیص داده شد، در حال رمزگشایی...")
            decoded_bytes = base64.b64decode(cleaned_content)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            logging.error(f"خطا در رمزگشایی Base64: {e}")
            return content
    return content

def parse_nodes(decoded_content: str) -> List[str]:
    """
    تمام لینک‌های کانفیگ معتبر را از محتوای متنی استخراج می‌کند.
    برای HTTP/HTTPS، فقط فرمت IP:PORT را می‌پذیرد.
    """
    nodes = []
    
    # الگوی IP:PORT. این الگو یک آدرس آی‌پی نسخه ۴ و یک پورت را تطبیق می‌دهد.
    # ^\d{1,3}(\.\d{1,3}){3}:\d{1,5}$
    ip_port_pattern = r'\d{1,3}(?:\.\d{1,3}){3}:\d{1,5}'
    
    # الگوی کامل برای پراکسی‌های HTTP/HTTPS
    # پشتیبانی از user:pass@IP:PORT و فقط IP:PORT
    http_proxy_pattern = re.compile(
        rf'^(https|http):\/\/(?:[^@]+@)?({ip_port_pattern})\/?$',
        re.IGNORECASE
    )

    # الگوی کلی برای سایر پروتکل‌ها
    other_protocol_pattern = re.compile(
        r'^(vless|vmess|trojan|ss|ssr|tuic|hy2|hysteria2|hysteria|snell|anytls|mieru|juicity|ssh|wireguard|warp|socks4|socks5|mtproto):\/\/',
        re.IGNORECASE
    )

    for line in decoded_content.splitlines():
        line = line.strip()
        if not line:
            continue
        
        # ابتدا بررسی می‌کنیم که آیا یک پراکسی HTTP/HTTPS با فرمت صحیح است
        if http_proxy_pattern.match(line):
            nodes.append(line)
        # سپس سایر پروتکل‌ها را بررسی می‌کنیم
        elif other_protocol_pattern.match(line):
            nodes.append(line)
            
    return nodes

def categorize_nodes(nodes: List[str]) -> Dict[str, List[str]]:
    """
    لیستی از نودها را بر اساس پروتکل آن‌ها دسته‌بندی می‌کند و نام‌های مستعار را نرمال‌سازی می‌کند.
    """
    categorized = {}
    
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
            continue
            
    return categorized
