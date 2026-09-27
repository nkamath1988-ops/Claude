"""Daily automation: price checks -> alerts, plus scheduled + price-drop-triggered
video generation. Run with `python -m skincare_dupe_bot.scheduler` and leave it
running (e.g. under systemd, tmux, or a cron-triggered one-shot invocation of
`run_price_check_job` / `run_video_rotation_job` if you'd rather not keep a
long-lived process alive on a laptop).
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func

from skincare_dupe_bot import config
from skincare_dupe_bot.alerts.email_alerts import send_price_drop_alerts
from skincare_dupe_bot.database.db import get_session, init_db
from skincare_dupe_bot.database.models import DrugstoreDupe, GeneratedVideo
from skincare_dupe_bot.scrapers.price_tracker import run_price_check
from skincare_dupe_bot.video.generator import generate_reel


def pick_dupes_for_rotation(session, n):
    """Least-recently-featured dupes first; never-featured dupes before all else."""
    last_used_subq = (
        session.query(GeneratedVideo.dupe_id, func.max(GeneratedVideo.created_at).label("last_used"))
        .group_by(GeneratedVideo.dupe_id)
        .subquery()
    )
    rows = (
        session.query(DrugstoreDupe)
        .outerjoin(last_used_subq, DrugstoreDupe.id == last_used_subq.c.dupe_id)
        .order_by(last_used_subq.c.last_used.is_(None).desc(), last_used_subq.c.last_used.asc())
        .limit(n)
        .all()
    )
    return rows


def run_price_check_job():
    print("[scheduler] running price check...")
    drops = run_price_check()
    print(f"[scheduler] price check done: {len(drops)} drop(s)")

    if drops:
        send_price_drop_alerts(drops)

        # Turn the single biggest drop into a reel too -- a real price
        # crash is worth breaking the normal rotation for.
        biggest = max(drops, key=lambda d: d.drop_pct)
        with get_session() as session:
            dupe = session.get(DrugstoreDupe, biggest.dupe_id)
            if dupe:
                kb = dupe.kbeauty_product
                path = generate_reel(kb, dupe, trigger_reason="price_drop")
                print(f"[scheduler] price-drop reel generated: {path}")


def run_video_rotation_job():
    print("[scheduler] running scheduled video rotation...")
    with get_session() as session:
        dupes = pick_dupes_for_rotation(session, config.VIDEOS_PER_RUN)
        # Detach the data we need before the session context closes.
        picks = [(d.kbeauty_product, d) for d in dupes]

    for kb, dupe in picks:
        path = generate_reel(kb, dupe, trigger_reason="scheduled_rotation")
        print(f"[scheduler] rotation reel generated: {path}")


def start():
    init_db()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_price_check_job, CronTrigger.from_crontab(config.PRICE_CHECK_CRON), id="price_check")
    scheduler.add_job(run_video_rotation_job, CronTrigger.from_crontab(config.VIDEO_GEN_CRON), id="video_rotation")
    print(
        f"[scheduler] started. price checks: '{config.PRICE_CHECK_CRON}', "
        f"video rotation: '{config.VIDEO_GEN_CRON}'"
    )
    scheduler.start()


if __name__ == "__main__":
    start()
