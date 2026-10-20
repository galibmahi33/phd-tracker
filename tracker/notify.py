"""Phone push through ntfy.sh. The topic name lives in the NTFY_TOPIC secret."""

import requests


def _line(rec: dict) -> str:
    where = ", ".join(p for p in (rec["university"], rec["country"]) if p)
    degrees = "/".join(rec["degrees"]) or "Position"
    funding = f", {rec['funding']}" if rec["funding"] != "Not stated" else ""
    return f"[{rec['relevance']}] {rec['poster_name'] or 'Unknown'}{f' ({where})' if where else ''}: {degrees}{funding}"


def send(topic: str, records: list[dict], dashboard_url: str, log) -> None:
    top = sorted(records, key=lambda r: r["relevance"], reverse=True)
    body = "\n".join(_line(r) for r in top[:6])
    if len(top) > 6:
        body += f"\n...and {len(top) - 6} more"
    title = f"{len(top)} new grad opening{'s' if len(top) != 1 else ''} match your profile"
    try:
        r = requests.post(
            f"https://ntfy.sh/{topic}",
            data=body.encode("utf-8"),
            headers={"Title": title, "Click": dashboard_url, "Tags": "mortar_board"},
            timeout=20,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"ntfy error: {e}")
