"""Email provider. Default: write to the local dev inbox (/dev-mail). SMTP is an optional plugin."""
from sqlalchemy.orm import Session

from clue.models import DevMail


def send_mail(db: Session, to: str, subject: str, body: str) -> None:
    db.add(DevMail(to=to, subject=subject, body=body))
    db.commit()
