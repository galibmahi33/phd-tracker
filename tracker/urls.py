"""URL helpers: canonical keys for dedupe and facts recoverable from LinkedIn URLs."""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit

# LinkedIn post URLs end in "-activity-<id>-xxxx" or "-ugcPost-<id>-xxxx";
# feed URLs use "urn:li:activity:<id>".
_LI_ID = re.compile(r"(?:activity|ugcPost|share)(?:-|:|%3A)(\d{16,20})", re.I)
_LI_POSTS_SLUG = re.compile(r"linkedin\.com/posts/([^_/?#]+)_", re.I)


def unwrap_redirect(url: str) -> str:
    """Google Alerts links go through google.com/url?url=<target>."""
    parts = urlsplit(url)
    if parts.netloc.endswith("google.com") and parts.path == "/url":
        target = parse_qs(parts.query).get("url") or parse_qs(parts.query).get("q")
        if target:
            return target[0]
    return url


def is_linkedin(url: str) -> bool:
    return "linkedin.com" in urlsplit(url).netloc.lower()


def linkedin_post_id(url: str) -> str | None:
    m = _LI_ID.search(url)
    return m.group(1) if m else None


def linkedin_post_date(post_id: str) -> str | None:
    """LinkedIn post IDs embed the creation time: the top 41 bits are Unix milliseconds."""
    try:
        ms = int(post_id) >> 22
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    if not 2015 <= dt.year <= 2035:
        return None
    return dt.date().isoformat()


def linkedin_slug(url: str) -> str | None:
    m = _LI_POSTS_SLUG.search(url)
    return unquote(m.group(1)) if m else None


def linkedin_profile_url(slug: str | None, poster_type: str) -> str:
    if not slug:
        return ""
    kind = "company" if poster_type == "organization" else "in"
    return f"https://www.linkedin.com/{kind}/{slug}/"


def canonical_url(url: str) -> str:
    """Strip tracking, fragments and country subdomains so the same page maps to one key."""
    url = unwrap_redirect(url.strip())
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.endswith("linkedin.com"):
        host = "www.linkedin.com"
    elif host in ("twitter.com", "www.twitter.com", "www.x.com", "mobile.x.com", "mobile.twitter.com"):
        host = "x.com"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, "", ""))


def dedupe_key(url: str) -> str:
    post_id = linkedin_post_id(url) if is_linkedin(url) else None
    if post_id:
        return f"li:{post_id}"
    return "url:" + canonical_url(url)


def safe_http_url(url: str) -> str:
    return url if url.lower().startswith(("https://", "http://")) else ""
