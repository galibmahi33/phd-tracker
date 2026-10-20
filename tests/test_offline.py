"""Offline checks for everything except the real Claude call (which is stubbed).

Run from the repository root:  python tests/test_offline.py
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracker import extract, prefilter, run, urls  # noqa: E402

TMP = ROOT / ".test-data"
FIXTURE = ROOT / "tests" / "sample_candidates.json"


def check_urls():
    u = "https://bd.linkedin.com/posts/jane-sample-12ab_phd-activity-7518100000000000000-AbCd?utm_source=x"
    assert urls.dedupe_key(u) == "li:7518100000000000000"
    assert urls.linkedin_post_date("7518100000000000000").startswith("2026-")
    assert urls.linkedin_slug(u) == "jane-sample-12ab"
    assert urls.linkedin_profile_url("jane-sample-12ab", "person") == "https://www.linkedin.com/in/jane-sample-12ab/"
    assert urls.canonical_url(u) == "https://www.linkedin.com/posts/jane-sample-12ab_phd-activity-7518100000000000000-AbCd"
    assert urls.unwrap_redirect("https://www.google.com/url?rct=j&url=https://example.edu/x&ct=ga") == "https://example.edu/x"
    assert urls.dedupe_key("https://Example.edu/lab/join/?a=1#top") == "url:https://example.edu/lab/join"
    assert urls.safe_http_url("javascript:alert(1)") == ""


def check_prefilter():
    assert prefilter.passes({"title": "Recruiting PhD students", "snippet": ""})
    assert prefilter.passes({"title": "Openings for MASc students", "snippet": "funding available"})
    assert not prefilter.passes({"title": "Join our webinar", "snippet": "radiology"})


def fake_classify(batch, profile, settings, today):
    out = {}
    for c in batch:
        good = "recruit" in c["title"].lower() or "positions" in c["title"].lower() or "openings" in c["snippet"].lower()
        out[c["key"]] = extract._normalize({
            "id": c["key"], "is_opportunity": good, "reject_reason": "" if good else "not recruitment",
            "poster_name": c["title"].split(" on LinkedIn")[0] if good else "", "poster_type": "person",
            "role": "Assistant Professor", "university": "Example State University" if "Jane" in c["title"] else "",
            "lab": "", "country": "USA", "research_areas": ["CT", "Domain Adaptation"],
            "degrees": ["PhD"], "funding": "Fully funded", "deadline": "2026-12-15",
            "deadline_text": "December 15", "start_term": "Fall 2027", "summary": "Sample summary.",
            "relevance": 88, "relevance_reason": "Sample reason.", "inferred_fields": ["role"],
        })
    return out


def check_pipeline():
    shutil.rmtree(TMP, ignore_errors=True)
    extract.classify = fake_classify
    for _ in range(2):  # second run must add nothing (dedupe)
        sys.argv = ["run", "--fixture", str(FIXTURE), "--data-dir", str(TMP), "--no-notify"]
        run.main()
    opps = json.loads((TMP / "opportunities.json").read_text(encoding="utf-8"))
    seen = json.loads((TMP / "seen.json").read_text(encoding="utf-8"))
    runs = json.loads((TMP / "runs.json").read_text(encoding="utf-8"))
    names = sorted(o["poster_name"] for o in opps)
    # Jane's two posts merge into one record with two links; the webinar is filtered out;
    # so is the MICCAI paper post; the lab page is accepted.
    assert len(opps) == 2, names
    jane = next(o for o in opps if o["poster_name"] == "Jane Sample")
    assert len(jane["links"]) == 2
    assert jane["profile_url"] == "https://www.linkedin.com/in/jane-sample-12ab/"
    assert jane["post_date"].startswith("2026-")
    assert seen["li:7518160000000000000"]["s"] == "filtered"
    assert seen["li:7518150000000000000"]["s"] == "filtered"  # paper news: no recruiting words
    assert runs[-1].get("new_candidates", 0) == 0 and runs[-1]["already_seen"] == 5
    assert not json.loads((TMP / "pending.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    check_urls()
    check_prefilter()
    check_pipeline()
    print("all offline checks passed")
