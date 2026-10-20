"""Collectors. Nothing here touches LinkedIn itself: LinkedIn posts arrive only as
search-engine results (Serper) or Google Alerts entries."""

import html
import re
import xml.etree.ElementTree as ET

import requests

from .urls import unwrap_redirect

SERPER_URL = "https://google.serper.dev/search"
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def serper(api_key: str, queries: list[dict], opts: dict, log) -> list[dict]:
    out = []
    for item in queries:
        body = {"q": item["q"], "gl": opts.get("gl", "us"), "hl": opts.get("hl", "en"), "num": opts.get("num", 10)}
        if item.get("tbs"):
            body["tbs"] = item["tbs"]
        try:
            r = requests.post(SERPER_URL, json=body, headers={"X-API-KEY": api_key}, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            log(f"serper error for [{item['q'][:60]}...]: {e}")
            continue
        for res in r.json().get("organic", []):
            link = res.get("link")
            if not link:
                continue
            out.append({
                "url": link,
                "source": item.get("source", "web"),
                "title": _clean(res.get("title", "")),
                "snippet": _clean(res.get("snippet", "")),
                "date_hint": res.get("date", ""),
            })
    return out


def feeds(urls: list[str], log) -> list[dict]:
    """Google Alerts (Atom) or any RSS/Atom feed."""
    out = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for feed_url in urls:
        try:
            r = requests.get(feed_url, timeout=30, headers={"User-Agent": "phd-tracker/1.0"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError) as e:
            log(f"feed error for {feed_url[:60]}: {e}")
            continue
        for entry in root.findall("a:entry", ns):
            link_el = entry.find("a:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            out.append({
                "url": unwrap_redirect(link),
                "source": "alert",
                "title": _clean(entry.findtext("a:title", "", ns)),
                "snippet": _clean(entry.findtext("a:content", "", ns)),
                "date_hint": entry.findtext("a:published", "", ns)[:10],
            })
        for item in root.iter("item"):
            out.append({
                "url": unwrap_redirect(item.findtext("link", "")),
                "source": "feed",
                "title": _clean(item.findtext("title", "")),
                "snippet": _clean(item.findtext("description", "")),
                "date_hint": item.findtext("pubDate", ""),
            })
    return [c for c in out if c["url"]]
