"""JSON storage, record building and cross-post merging."""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .urls import canonical_url, is_linkedin, linkedin_profile_url, linkedin_slug, safe_http_url

MERGE_WINDOW_DAYS = 60
_HONORIFIC = re.compile(r"^(?:dr|prof|professor|mr|ms|mrs|mx)\.?\s+", re.I)
_TITLE_NAME = re.compile(r"^(.+?)(?: on LinkedIn\b|'s Post\b| - LinkedIn\b)", re.I)


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _norm_name(name: str) -> str:
    name = name.strip().lower()
    while _HONORIFIC.match(name):
        name = _HONORIFIC.sub("", name, count=1)
    return re.sub(r"[^a-z]", "", name)


def _day(rec: dict) -> date:
    raw = rec.get("post_date") or rec.get("first_seen", "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def make_record(cand: dict, res: dict, stamp: str) -> dict:
    url = cand["url"]
    post_url = canonical_url(url) if is_linkedin(url) else safe_http_url(url)
    name = res["poster_name"]
    if not name:
        m = _TITLE_NAME.match(cand.get("title", ""))
        name = m.group(1).strip() if m else ""
    slug = linkedin_slug(url) if is_linkedin(url) else None
    return {
        "id": cand["key"],
        "first_seen": stamp,
        "last_seen": stamp,
        "post_date": cand.get("post_date") or "",
        "poster_name": name,
        "poster_type": res["poster_type"],
        "role": res["role"],
        "university": res["university"],
        "lab": res["lab"],
        "country": res["country"],
        "research_areas": res["research_areas"],
        "degrees": res["degrees"],
        "funding": res["funding"],
        "deadline": res["deadline"],
        "deadline_text": res["deadline_text"],
        "start_term": res["start_term"],
        "summary": res["summary"],
        "relevance": res["relevance"],
        "relevance_reason": res["relevance_reason"],
        "inferred_fields": res["inferred_fields"],
        "source": cand["source"],
        "post_url": post_url,
        "profile_url": linkedin_profile_url(slug, res["poster_type"]),
        "title": cand.get("title", ""),
        "snippet": cand.get("snippet", ""),
        "links": [{"url": post_url, "source": cand["source"]}],
    }


def find_duplicate(opps: list[dict], rec: dict) -> dict | None:
    """Same person, same (or unknown) university, overlapping degrees, posted close together."""
    name = _norm_name(rec["poster_name"])
    if not name:
        return None
    for old in opps:
        if _norm_name(old["poster_name"]) != name:
            continue
        if old["university"] and rec["university"] and old["university"].lower() != rec["university"].lower():
            continue
        if old["degrees"] and rec["degrees"] and not set(old["degrees"]) & set(rec["degrees"]):
            continue
        if abs((_day(old) - _day(rec)).days) <= MERGE_WINDOW_DAYS:
            return old
    return None


def merge(old: dict, new: dict) -> None:
    if all(link["url"] != new["post_url"] for link in old["links"]):
        old["links"].append({"url": new["post_url"], "source": new["source"]})
    for field in ("role", "university", "lab", "country", "deadline", "deadline_text", "start_term",
                  "profile_url", "post_date"):
        if not old.get(field) and new.get(field):
            old[field] = new[field]
    if old["funding"] == "Not stated":
        old["funding"] = new["funding"]
    old["degrees"] = sorted(set(old["degrees"]) | set(new["degrees"]))
    old["research_areas"] = list(dict.fromkeys(old["research_areas"] + new["research_areas"]))[:5]
    old["relevance"] = max(old["relevance"], new["relevance"])
    old["last_seen"] = new["first_seen"]


def prune_seen(seen: dict, today: str, days: int) -> dict:
    cutoff = (datetime.fromisoformat(today) - timedelta(days=days)).date().isoformat()
    return {k: v for k, v in seen.items() if v.get("d", today) >= cutoff}
