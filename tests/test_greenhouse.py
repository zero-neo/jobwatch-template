from jobwatch.models import Company
from jobwatch.sources import greenhouse

COMPANY = Company("Acme", "greenhouse", "acme")
PAYLOAD = {
    "jobs": [
        {
            "id": 4001,
            "title": " Research Engineer ",
            "updated_at": "2026-10-01T10:00:00-04:00",
            "location": {"name": "Berlin"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/4001",
            "content": "&lt;p&gt;Fish &amp;amp; chips, in &lt;b&gt;Python&lt;/b&gt;&lt;/p&gt;",
        },
        {"id": 4002, "title": "Designer", "location": None, "absolute_url": "u"},
    ]
}


def test_parse():
    jobs = greenhouse.parse(COMPANY, PAYLOAD)
    assert len(jobs) == 2
    first = jobs[0]
    assert first.title == "Research Engineer"
    assert first.location == "Berlin"
    assert first.external_id == "4001"
    assert first.description == "Fish & chips, in Python"
    assert first.posted == "2026-10-01T10:00:00-04:00"
    assert jobs[1].location == ""


def test_fetch_uses_session():
    calls = {}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return PAYLOAD

    class Session:
        def get(self, url, params, timeout):
            calls.update(url=url, params=params)
            return Resp()

    assert len(greenhouse.fetch(COMPANY, session=Session())) == 2
    assert calls["url"].endswith("/boards/acme/jobs")
    assert calls["params"] == {"content": "true"}
