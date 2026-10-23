"""Daily pipeline: collect -> dedupe -> keyword filter -> Claude -> store -> notify.

Usage:
  python -m tracker.run                       # normal run (GitHub Actions)
  python -m tracker.run --fixture FILE --data-dir DIR --no-notify   # local test
"""

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import collect, extract, notify, prefilter, store
from .urls import dedupe_key, is_linkedin, linkedin_post_date, linkedin_post_id, unwrap_redirect

ROOT = Path(__file__).resolve().parent.parent
MAX_ATTEMPTS = 3
RUNS_KEPT = 120


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="JSON list of candidates to use instead of the collectors")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    queries = json.loads((ROOT / "config" / "queries.json").read_text(encoding="utf-8"))
    data_dir = Path(args.data_dir)
    now = datetime.now(timezone.utc)
    today, stamp = now.date().isoformat(), now.isoformat(timespec="seconds")

    errors: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        errors.append(msg)

    opps = store.load(data_dir / "opportunities.json", [])
    seen = store.load(data_dir / "seen.json", {})
    pending = store.load(data_dir / "pending.json", [])
    runs = store.load(data_dir / "runs.json", [])
    stats = Counter()

    # 1. Collect
    if args.fixture:
        raw = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    else:
        raw = []
        if os.environ.get("SERPER_API_KEY"):
            raw += collect.serper(os.environ["SERPER_API_KEY"], queries, settings["serper"], log)
        else:
            log("SERPER_API_KEY is not set; skipping search")
        feed_urls = [u.strip() for u in os.environ.get("ALERT_FEEDS", "").splitlines() if u.strip()]
        raw += collect.feeds(feed_urls + settings.get("feeds", []), log)

    # 2. Dedupe + free keyword filter
    pending_keys = {c["key"] for c in pending}
    for cand in raw:
        stats["collected"] += 1
        cand["url"] = unwrap_redirect(cand["url"])
        key = dedupe_key(cand["url"])
        if key in seen or key in pending_keys:
            stats["already_seen"] += 1
            continue
        cand["key"] = key
        post_id = linkedin_post_id(cand["url"]) if is_linkedin(cand["url"]) else None
        cand["post_date"] = linkedin_post_date(post_id) if post_id else ""
        if not prefilter.passes(cand):
            seen[key] = {"d": today, "s": "filtered"}
            stats["filtered_out"] += 1
            continue
        cand["attempts"] = 0
        pending.append(cand)
        pending_keys.add(key)
        stats["new_candidates"] += 1

    # 3. Claude (unprocessed candidates stay pending and are retried next run)
    profile = os.environ.get("PROFILE_TEXT") or (ROOT / "config" / "profile_fallback.md").read_text(encoding="utf-8")
    todo = pending[: settings["max_candidates_per_run"]]
    size = settings["batch_size"]
    done: set[str] = set()
    new_records: list[dict] = []
    for i in range(0, len(todo), size):
        batch = todo[i:i + size]
        for cand in batch:
            cand["attempts"] = cand.get("attempts", 0) + 1
        try:
            results = extract.classify(batch, profile, settings, today)
        except Exception as e:  # auth, usage limit, CLI failure: stop and retry tomorrow
            log(f"claude error: {e}")
            stats["claude_errors"] += 1
            break
        stats["sent_to_claude"] += len(batch)
        for cand in batch:
            res = results.get(cand["key"])
            if res is None:
                if cand["attempts"] >= MAX_ATTEMPTS:
                    seen[cand["key"]] = {"d": today, "s": "skipped"}
                    done.add(cand["key"])
                continue
            done.add(cand["key"])
            if res["is_opportunity"]:
                rec = store.make_record(cand, res, stamp)
                dup = store.find_duplicate(opps, rec)
                if dup:
                    store.merge(dup, rec)
                    stats["merged"] += 1
                else:
                    opps.append(rec)
                    new_records.append(rec)
                    stats["accepted"] += 1
                seen[cand["key"]] = {"d": today, "s": "accepted"}
            else:
                seen[cand["key"]] = {"d": today, "s": "rejected", "why": res["reject_reason"][:120]}
                stats["rejected"] += 1
    pending = [c for c in pending if c["key"] not in done]

    # 4. Save
    opps.sort(key=lambda r: r["first_seen"], reverse=True)
    seen = store.prune_seen(seen, today, settings["seen_retention_days"])
    runs.append({"at": stamp, **stats, "pending": len(pending), "errors": errors[:20]})
    store.save(data_dir / "opportunities.json", opps)
    store.save(data_dir / "seen.json", seen)
    store.save(data_dir / "pending.json", pending)
    store.save(data_dir / "runs.json", runs[-RUNS_KEPT:])

    # 5. Notify: one daily summary, every run
    threshold = settings["notify_min_relevance"]
    problems = []
    if stats["claude_errors"]:
        problems.append("Claude step failed (expired token or usage limit). "
                        f"{len(pending)} posts are saved and will be retried tomorrow.")
    search_failures = sum(e.startswith("serper error") for e in errors)
    if any(e.startswith("SERPER_API_KEY") for e in errors) or search_failures > len(queries) // 3:
        problems.append("Search failed (check the Serper key or credits).")
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic and not args.no_notify:
        notify.send_daily(topic, new_records, threshold, problems, settings["dashboard_url"], log)

    strong = sum(r["relevance"] >= threshold for r in new_records)
    print(json.dumps({**stats, "pending": len(pending), "strong_new": strong}, indent=1))


if __name__ == "__main__":
    main()
