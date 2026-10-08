from jobwatch.models import Company
from jobwatch.sources import lever

COMPANY = Company("Acme", "lever", "acme")
PAYLOAD = [
    {
        "id": "abc-123",
        "text": " Machine Learning Engineer ",
        "hostedUrl": "https://jobs.lever.co/acme/abc-123",
        "createdAt": 1759310400000,  # 2025-10-01T09:20:00Z
        "categories": {"location": "Berlin", "allLocations": ["Berlin", "Remote - Germany"]},
        "descriptionPlain": "Build models in Python.",
        "additionalPlain": "We value Bayesian thinking.",
        "lists": [{"text": "Requirements", "content": "<li>PhD in <b>neuroscience</b></li>"}],
    },
    {"id": "def-456", "text": "Designer", "hostedUrl": "u", "categories": {}},
]


def test_parse():
    jobs = lever.parse(COMPANY, PAYLOAD)
    first = jobs[0]
    assert first.title == "Machine Learning Engineer"
    assert first.location == "Berlin | Remote - Germany"
    assert first.external_id == "abc-123"
    assert first.posted == "2025-10-01T09:20:00+00:00"
    assert "Bayesian" in first.description and "neuroscience" in first.description
    assert "<" not in first.description
    assert jobs[1].location == "" and jobs[1].posted is None


def test_fetch_and_eu_endpoint():
    seen = []

    class Resp:
        def raise_for_status(self): pass
        def json(self): return PAYLOAD

    class Session:
        def get(self, url, params, timeout):
            seen.append((url, params))
            return Resp()

    assert len(lever.fetch(COMPANY, session=Session())) == 2
    assert len(lever.fetch_eu(COMPANY, session=Session())) == 2
    assert seen[0] == ("https://api.lever.co/v0/postings/acme", {"mode": "json"})
    assert seen[1][0] == "https://api.eu.lever.co/v0/postings/acme"
