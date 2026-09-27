"""SMTP price-drop email alerts.

Requires SMTP_USERNAME / SMTP_PASSWORD env vars to actually send (an app
password, not a real account password -- see README). With those unset,
send_price_drop_alerts logs what it would have sent instead of failing.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from skincare_dupe_bot import config
from skincare_dupe_bot.database.db import get_session
from skincare_dupe_bot.database.models import AlertLog
from skincare_dupe_bot.scrapers.price_tracker import PriceDrop


def _build_email_body(drops: List[PriceDrop]) -> str:
    lines = ["Price drops on your K-beauty dupe list:", ""]
    for d in drops:
        lines.append(
            f"- {d.brand} {d.name}: ${d.old_price:.2f} -> ${d.new_price:.2f} "
            f"({d.drop_pct:.0f}% off)\n  {d.product_url}"
        )
    return "\n".join(lines)


def send_price_drop_alerts(drops: List[PriceDrop]) -> bool:
    if not drops:
        return False

    subject = f"{len(drops)} skincare dupe price drop(s)"
    body = _build_email_body(drops)

    if not config.SMTP_USERNAME or not config.SMTP_PASSWORD:
        print("[email_alerts] SMTP_USERNAME/SMTP_PASSWORD not set -- logging instead of sending:")
        print(f"To: {config.ALERT_RECIPIENT}\nSubject: {subject}\n\n{body}")
        return False

    msg = MIMEMultipart()
    msg["From"] = config.SMTP_USERNAME
    msg["To"] = config.ALERT_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(msg)

    with get_session() as session:
        for d in drops:
            session.add(AlertLog(dupe_id=d.dupe_id, old_price=d.old_price, new_price=d.new_price))

    print(f"[email_alerts] sent alert for {len(drops)} drop(s) to {config.ALERT_RECIPIENT}")
    return True
