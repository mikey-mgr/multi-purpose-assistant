"""
Shared utilities for scrapers (no circular imports).
"""


class SiteScrapeError(Exception):
    """Raised when a site scrape should be retried (e.g. 403)."""
    def __init__(self, site: str, message: str, retry_after: int = 60):
        self.site = site
        self.retry_after = retry_after
        super().__init__(message)


def decode_cfemail(cfemail_hex: str) -> str | None:
    """Decode Cloudflare Email Protection encoded email (XOR with first byte)."""
    if not cfemail_hex:
        return None
    try:
        raw = bytes.fromhex(cfemail_hex)
        key = raw[0]
        return ''.join(chr(b ^ key) for b in raw[1:])
    except Exception:
        return None


def render_links(soup) -> str:
    """Replace `<a>` tags with ``text (url)`` preserving both, then return text."""
    for a in soup.find_all('a', href=True):
        href = a['href']
        txt = a.get_text(strip=True) or href
        a.replace_with(f'{txt} ({href})')
    return soup.get_text(separator='\n', strip=True)
