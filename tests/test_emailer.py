import pytest

from jobwatch import emailer
from jobwatch.models import Job
from jobwatch.storage import Store

CFG = {"host": "h", "port": 587, "user": "u", "password": "p", "to": "me@x.org", "sender": "me@x.org"}


def mk(i, company="Acme"):
    return Job("greenhouse", str(i), f"Role {i}", company, "Berlin", f"http://x/{i}", None, "")


class FakeServer:
    sent = []

    def __init__(self, fail=False):
        self.fail = fail

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def send_message(self, msg):
        if self.fail:
            raise RuntimeError("rejected")
        FakeServer.sent.append(msg)


def test_message_groups_by_company_and_truncates():
    jobs = [mk(i, "Zed" if i % 2 else "Acme") for i in range(emailer.MAX_LISTED + 5)]
    msg = emailer.build_message(jobs, "a@x", "b@x", "http://sheet")
    body = msg.get_content()
    assert msg["Subject"] == f"jobwatch: {len(jobs)} new jobs"
    assert body.index("Acme") < body.index("Zed")
    assert "...and 5 more." in body and "All jobs: http://sheet" in body
    assert emailer.build_message([mk(1)], "a@x", "b@x")["Subject"] == "jobwatch: 1 new job"


def test_notify_marks_only_after_success(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "t.sqlite"))
    store.add_new([mk(1), mk(2)])
    monkeypatch.setattr(emailer, "_connect", lambda cfg: FakeServer(fail=True))
    with pytest.raises(RuntimeError):
        emailer.notify(store, CFG)
    assert len(store.pending("notified")) == 2
    FakeServer.sent = []
    monkeypatch.setattr(emailer, "_connect", lambda cfg: FakeServer())
    assert emailer.notify(store, CFG) == 2
    assert len(FakeServer.sent) == 1 and store.pending("notified") == []
    assert emailer.notify(store, CFG) == 0 and len(FakeServer.sent) == 1


def test_not_configured(tmp_path, monkeypatch):
    for var in ("SMTP_HOST", "EMAIL_TO", "SMTP_USER"):
        monkeypatch.delenv(var, raising=False)
    assert emailer.notify_from_env(Store(str(tmp_path / "t.sqlite"))) is None
    assert "not configured" in emailer.check_email()


def test_check_email_login_failure_hint(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("EMAIL_TO", "me@x.org")

    def boom(cfg):
        raise RuntimeError("535 bad credentials")

    monkeypatch.setattr(emailer, "_connect", boom)
    assert "app password" in emailer.check_email()


def test_gmail_defaults(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "EMAIL_TO", "EMAIL_FROM"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    cfg = emailer._settings()
    assert (cfg["host"], cfg["port"], cfg["to"], cfg["sender"]) == (
        "smtp.gmail.com", 587, "me@gmail.com", "me@gmail.com")
