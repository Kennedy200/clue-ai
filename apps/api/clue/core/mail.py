"""Email. Every message is stored in the local dev inbox. If SMTP_HOST is set it is also sent for real (any SMTP server,
for example a free Brevo or Gmail app-password account). Sending failures are logged and never break the request."""
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from clue.core.config import get_settings
from clue.models import DevMail

log = logging.getLogger("clue.mail")


def smtp_configured() -> bool:
    return bool(get_settings().smtp_host)


def _smtp_send(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.smtp_from or s.smtp_user or f"noreply@{s.smtp_host}"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if s.smtp_port == 465:
        server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20)
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
    with server:
        if s.smtp_port != 465 and s.smtp_starttls:
            server.starttls()
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)


def send_mail(db: Session, to: str, subject: str, body: str) -> None:
    db.add(DevMail(to=to, subject=subject, body=body))
    db.commit()
    if smtp_configured():
        try:
            _smtp_send(to, subject, body)
        except Exception as e:  # noqa: BLE001
            log.error("SMTP send to %s failed: %s", to, e.__class__.__name__)
