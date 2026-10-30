"""Weekly summary push through ntfy.sh. The topic name lives in the NTFY_TOPIC secret.

One notification per run: high priority when something scores at or above the threshold
or the run had a problem, normal when there are only weaker new posts, low when nothing is new.
"""

import requests

TOP_N = 5


def _line(rec: dict) -> str:
    where = ", ".join(p for p in (rec["university"], rec["country"]) if p)
    degrees = "/".join(rec["degrees"]) or "Position"
    funding = f", {rec['funding']}" if rec["funding"] != "Not stated" else ""
    return f"[{rec['relevance']}] {rec['poster_name'] or 'Unknown'}{f' ({where})' if where else ''}: {degrees}{funding}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def send_summary(topic: str, new_records: list[dict], threshold: int, problems: list[str],
               dashboard_url: str, log) -> None:
    top = sorted(new_records, key=lambda r: r["relevance"], reverse=True)
    strong = [r for r in top if r["relevance"] >= threshold]

    if strong:
        title = f"{_plural(len(strong), 'strong match')} this week ({len(top)} new in total)"
        priority, tags = "high", "star,mortar_board"
    elif top:
        title = f"{_plural(len(top), 'new post')} this week, none scored {threshold}+"
        priority, tags = "default", "mortar_board"
    else:
        title = "No new openings this week"
        priority, tags = "low", "zzz"

    lines = [_line(r) for r in top[:TOP_N]]
    if len(top) > TOP_N:
        lines.append(f"...and {len(top) - TOP_N} more on the dashboard")
    if not top:
        lines.append("The tracker ran normally and found nothing new.")
    if problems:
        title = "Tracker problem: " + title
        priority, tags = "high", "warning"
        lines = [f"Problem: {p}" for p in problems] + [""] + lines

    try:
        r = requests.post(
            f"https://ntfy.sh/{topic}",
            data="\n".join(lines).encode("utf-8"),
            headers={"Title": title, "Priority": priority, "Tags": tags, "Click": dashboard_url},
            timeout=20,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"ntfy error: {e}")
