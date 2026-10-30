# PhD Opportunity Tracker

A weekly-updated dashboard of PhD and Master's recruitment posts in medical imaging, AI in medicine
and related areas, ranked by fit with my research profile.

**Dashboard:** https://galibmahi33.github.io/phd-tracker/

## How it works

Every Wednesday morning (scheduled for 05:17 Bangladesh time; GitHub may start it a little late), a GitHub Actions job (`.github/workflows/update.yml`):

1. **Collects** candidate posts. LinkedIn is never accessed directly. LinkedIn posts arrive only as
   Google search results (via the Serper API, `site:linkedin.com/posts` queries in
   `config/queries.json`) and optional Google Alerts RSS feeds. A few queries also cover X and
   university (`.edu`/`.ca`) pages.
2. **Removes duplicates.** Every LinkedIn post has a unique ID in its URL. Anything seen before
   is skipped (`data/seen.json`).
3. **Applies a free keyword filter.** A result must mention a degree (PhD, Master's, RA...) and recruiting language.
4. **Screens and scores with Claude** (Sonnet, run through Claude Code on a Claude subscription,
   with all tools disabled). Claude rejects non-recruitment posts, extracts the fields and gives a
   0-100 match score against my profile (the `PROFILE_TEXT` secret).
5. **Stores** results in `data/opportunities.json` and merges cross-posts (same professor, same
   opening) into one entry with several links.
6. **Publishes** the dashboard (`docs/`) to GitHub Pages and sends one ntfy summary notification per run (high priority when new
   posts score 60 or more, or when something went wrong).

If Claude fails on a given day (e.g. a usage limit), the candidates stay in `data/pending.json` and are retried
on the next run.

## Secrets (Settings → Secrets and variables → Actions)

| Secret | What it is |
|---|---|
| `SERPER_API_KEY` | Serper search API key |
| `CLAUDE_CODE_OAUTH_TOKEN` | Output of `claude setup-token` (uses the Claude subscription) |
| `PROFILE_TEXT` | Private research profile used for scoring |
| `NTFY_TOPIC` | ntfy topic name for phone notifications |
| `ALERT_FEEDS` | Optional: Google Alerts RSS URLs, one per line |

## Tuning

- `config/queries.json`: search queries (each costs one Serper credit per run).
- `config/settings.json`: model, batch size, notification threshold, target countries.
- To run it now: Actions tab → **Update opportunities** → **Run workflow**.

## Testing locally

```
python tests/test_offline.py
```

## Limits

Search engines index only some LinkedIn posts, often days late, and posts visible only to
connections never show up. Deadlines and funding are often missing from posts. Fields the model
inferred are underlined on the dashboard. Always open the original post before acting.
