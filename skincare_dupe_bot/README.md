# K-Beauty Dupe Tracker

Tracks drugstore/mass-market dupes for popular Korean skincare products,
watches their prices, emails you when one drops, and auto-generates short
vertical "reel" videos (script + text-card visuals + AI voiceover) ready to
upload to TikTok/Instagram/Shorts.

Built for zero capital: no paid APIs, no proxies, no ad spend. Everything
here runs on free tools (SQLite, gTTS, ffmpeg, a headless Chromium already
installed in this environment) or things you already have (an email
account, a phone to upload from).

## What's real vs. what needs you

| Piece | Status |
|---|---|
| Dupe database (30 K-beauty products, 31 drugstore/mass dupes) | Done, manually curated |
| Price tracking | **Works against target.com only** (see below) |
| Email price-drop alerts | Works once you set SMTP env vars |
| Auto-generated reels (script + visuals + voiceover) | Done, fully automated |
| Posting reels to social platforms | **Not built** -- needs your own developer app approval (see below) |
| Web dashboard | Done (search, price history, manual triggers) |

## Honest limitation: only target.com actually scrapes

I tested all four obvious drugstore-adjacent retailers from this
environment's network before building anything further:

- **target.com** -- works. A headless browser gets real, current prices.
- **cvs.com** -- blocked at the CDN/WAF edge (Akamai "Access Denied",
  HTTP 403) before the page even loads. Not a JS challenge to solve --
  an IP-level deny that a smarter scraper doesn't fix.
- **amazon.com** -- blocked by an Akamai bot-management interstitial
  (a proof-of-work JS page, not real search results).
- **walgreens.com** -- returns a near-empty page, no usable content
  (likely PerimeterX or similar).

The tracker always tries target.com first and falls back to amazon.com as
a best-effort second attempt (amazon.py is kept in case a different
network, e.g. your own home connection, isn't blocked the same way -- test
before trusting it). **Do not spend time trying to "fix" the cvs.com or
walgreens.com scraping without a paid residential-proxy service** -- that
would cost money and defeat the reason this was built the way it was.

Realistic consequence: on a first full price-check run against the 31
seeded dupes, about 4 resolved to a real, current price. The rest either
aren't carried on target.com under that search term, or my title-matching
heuristic (see `scrapers/base.py`) was too conservative to confidently
match them. This is a known v1 gap, not a hidden one -- tightening title
matching or adding more retailers is the natural next step if this gets
used for real.

## Why text cards instead of product photos

The reels use styled text cards (brand/product/price on a colored
background), not scraped product photography. Redistributing retailer or
brand product photos inside monetized video content is real
copyright/trademark exposure; text cards sidestep that entirely at the
cost of visual polish. If this grows, licensed or self-shot photography
would be the next investment, not more scraping.

## Auto-posting to social media: not included, on purpose

TikTok's Content Posting API and Instagram's Graph API both require a
registered developer app tied to *your* identity/business, plus (for
TikTok) an audit before it can post on your behalf. That's not something
this session can obtain for you -- it has to be your app, your approval.
Generated videos land in `output/ready_to_upload/` with a matching
`.txt` file (caption + hashtags) next to each one; you upload manually
until/unless you wire up those APIs yourself.

## Setup

```bash
python3 -m venv .venv_skincare
.venv_skincare/bin/pip install -r requirements.txt
.venv_skincare/bin/python -m playwright install chromium  # skip if using this environment's preinstalled Chromium at /opt/pw-browsers
.venv_skincare/bin/python -m skincare_dupe_bot.database.seed
```

Copy `.env.example` to `.env` and fill in SMTP credentials (a Gmail App
Password, not your real password) to get real email alerts instead of
console-logged ones.

## Running it

```bash
# One-off price check + alert
.venv_skincare/bin/python -m skincare_dupe_bot.scrapers.price_tracker

# Generate one reel right now (rotates through least-recently-featured dupes)
.venv_skincare/bin/python -c "from skincare_dupe_bot.scheduler import run_video_rotation_job; run_video_rotation_job()"

# Web dashboard (search dupes, view price history, manually trigger checks/videos)
.venv_skincare/bin/python -m skincare_dupe_bot.web.app
# -> http://127.0.0.1:5000

# Full automation: daily price checks (9am) + daily video rotation (10am),
# plus an extra reel whenever a price check finds a real drop
.venv_skincare/bin/python -m skincare_dupe_bot.scheduler
```

The scheduler is a long-running process -- run it under `tmux`, `systemd`,
or similar if you want it surviving a logout. On a laptop that isn't
always on, running `price_tracker` and the rotation job from cron/Task
Scheduler when the machine happens to be on is more realistic than a
24/7 daemon.

## Extending the dupe list

Add entries to `data/dupes_seed.json` (same shape as the existing 30) and
re-run the seed script -- it's idempotent, matching on (brand, name) so
re-running never duplicates rows.

## Project layout

```
skincare_dupe_bot/
  config.py              # all settings, env-var overridable
  database/               # SQLAlchemy models, seed loader, seed data
  scrapers/                # target.com (works), amazon.com (best-effort), shared helpers
  alerts/                  # SMTP price-drop emails
  video/                    # script templates, PIL text-card renderer, ffmpeg/gTTS assembly
  scheduler.py              # APScheduler cron jobs tying it together
  web/                      # Flask dashboard
  output/videos/            # every generated reel (source of truth)
  output/ready_to_upload/   # copy + caption/hashtags .txt, for manual upload
```
