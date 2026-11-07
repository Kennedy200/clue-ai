import smtplib

from sqlalchemy import select

from clue.core import mail
from clue.core.config import get_settings
from clue.models import DevMail
from tests.conftest import signup


class FakeSMTP:
    sent: list = []
    fail = False

    def __init__(self, host, port, timeout=0):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.tls = True

    def login(self, u, p):
        self.cred = (u, p)

    def send_message(self, msg):
        if FakeSMTP.fail:
            raise smtplib.SMTPException("down")
        FakeSMTP.sent.append((self.host, self.port, msg["To"], msg["Subject"], msg.get_content()))


def test_mail_goes_out_through_smtp_when_configured(client, db, monkeypatch):
    s = get_settings()
    for k, v in {"smtp_host": "smtp.example.com", "smtp_user": "u", "smtp_password": "p", "smtp_from": "Clue <no@x.com>"}.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent, FakeSMTP.fail = [], False
    signup(client, "new@example.com")
    assert FakeSMTP.sent and FakeSMTP.sent[0][2] == "new@example.com" and "Verify" in FakeSMTP.sent[0][3] and "/verify?token=" in FakeSMTP.sent[0][4]
    assert db.scalar(select(DevMail).where(DevMail.to == "new@example.com"))  # still kept locally


def test_a_broken_mail_server_never_breaks_signup(client, db, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent, FakeSMTP.fail = [], True
    signup(client, "ok@example.com")  # would raise if the SMTP error leaked out


def test_without_smtp_nothing_is_sent(client, monkeypatch):
    assert not mail.smtp_configured()
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not connect")))
    signup(client, "quiet@example.com")
