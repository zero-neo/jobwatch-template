import pytest
import requests

from jobwatch import boards
from jobwatch.__main__ import main
from jobwatch.config import ConfigError, Filters
from jobwatch.filters import JobFilter
from jobwatch.models import Job
from jobwatch.sources import adzuna

ITEM = {
    "id": "111", "title": "Senior <strong>Data</strong> Scientist",
    "company": {"display_name": "Acme AG"}, "location": {"display_name": "Zürich, Kanton Zürich"},
    "description": "Build <b>models</b> &amp; dashboards", "redirect_url": "https://adzuna/x",
    "created": "2026-10-01T10:00:00Z",
}


class Resp:
    def __init__(self, payload=None, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


def test_parse_cleans_text_and_adds_country():
    job = adzuna.parse("ch", {"results": [ITEM]})[0]
    assert job.title == "Senior Data Scientist"
    assert job.location == "Zürich, Kanton Zürich, Switzerland"
    assert job.company == "Acme AG" and job.description == "Build models & dashboards"
    assert job.source == "adzuna" and job.posted == "2026-10-01T10:00:00Z"


def test_country_not_duplicated_when_present():
    item = dict(ITEM, location={"display_name": "Berlin, Germany"})
    assert adzuna.parse("de", {"results": [item]})[0].location == "Berlin, Germany"


def test_pagination_stops_on_short_page():
    pages = []

    class Session:
        def get(self, url, params, timeout):
            pages.append(url.rsplit("/", 1)[1])
            n = adzuna.PAGE_SIZE if len(pages) == 1 else 3
            return Resp({"results": [dict(ITEM, id=f"{len(pages)}-{i}") for i in range(n)]})

    jobs = adzuna.fetch_query("de", "data", 5, 14, "id", "key", session=Session())
    assert len(jobs) == adzuna.PAGE_SIZE + 3 and pages == ["1", "2"]


def test_errors_never_leak_the_api_key():
    class Boom:
        def get(self, url, params, timeout):
            raise requests.ConnectionError(f"failed for {url}?app_key=SECRET")

    class Denied:
        def get(self, url, params, timeout):
            return Resp(status=401)

    for session in (Boom(), Denied()):
        with pytest.raises(RuntimeError) as err:
            adzuna.fetch_query("de", "q", 1, 14, "id", "SECRET", session=session)
        assert "SECRET" not in str(err.value) and "SECRET" not in repr(err.value.__cause__)


def mk(i, title="Data Scientist", location="Berlin, Germany"):
    return Job("adzuna", str(i), title, "Acme", location, "u", None, "")


def test_collect_filters_dedupes_and_survives_failures():
    f = JobFilter(Filters(title_include=["data scien*"], locations=["Germany", "Switzerland"]))
    search = boards.AdzunaSearch(["de", "ch"], ["a", "b"])

    def fetch(country, query, pages, days, app_id, app_key):
        if (country, query) == ("ch", "a"):
            raise RuntimeError("HTTP 400")
        return [mk(1), mk(2, title="Plumber"), mk(3, location="Paris, France")]

    matched, errors = boards.collect_adzuna(search, f, fetch=fetch)
    assert [j.external_id for j in matched] == ["1"]
    assert len(errors) == 1 and "ch 'a'" in errors[0]


def test_missing_credentials_message(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    matched, errors = boards.collect_adzuna(boards.AdzunaSearch(["de"], ["x"]), JobFilter(Filters(["x"])))
    assert matched == [] and "ADZUNA_APP_ID" in errors[0]


def test_load_searches_validation(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("adzuna:\n  countries: [DE, nl]\n  queries: [data scientist]\n")
    s = boards.load_searches(p)
    assert s.countries == ["de", "nl"] and s.max_pages == 2 and s.max_days_old == 14
    for bad in ("adzuna:\n  countries: [xx]\n  queries: [a]\n",
                "adzuna:\n  countries: [de]\n  queries: []\n",
                "adzuna:\n  countries: [de]\n  queries: [a]\n  max_pages: 99\n",
                "adzuna:\n  countries: [de]\n  queries: [a]\n  pages: 2\n",
                "other: 1\n"):
        p.write_text(bad)
        with pytest.raises(ConfigError):
            boards.load_searches(p)


def test_shipped_template_loads():
    s = boards.load_searches("searches.yaml")
    assert s.countries == ["de"] and s.queries


def test_main_runs_searches_without_companies(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("jobwatch.__main__.load_dotenv", lambda *a, **k: None)
    (tmp_path / "config.yaml").write_text("title_include: [data scien*]\n")
    (tmp_path / "companies.yaml").write_text("companies: []\n")
    (tmp_path / "searches.yaml").write_text("adzuna:\n  countries: [nl]\n  queries: [data]\n")
    monkeypatch.setattr("jobwatch.__main__.collect_adzuna",
                        lambda s, f: ([mk(7, location="Amsterdam, Netherlands")], []))
    assert main(["--dry-run"]) == 0
    assert "Amsterdam" in capsys.readouterr().out


def test_temporary_errors_are_retried(monkeypatch):
    monkeypatch.setattr(adzuna.time, "sleep", lambda s: None)
    codes = iter([503, 503, 200])

    class Session:
        def get(self, url, params, timeout):
            code = next(codes)
            return Resp({"results": [ITEM]} if code == 200 else None, status=code)

    assert len(adzuna.fetch_query("de", "q", 1, 14, "id", "k", session=Session())) == 1


def test_gives_up_after_three_attempts(monkeypatch):
    monkeypatch.setattr(adzuna.time, "sleep", lambda s: None)
    calls = []

    class Session:
        def get(self, url, params, timeout):
            calls.append(1)
            return Resp(status=503)

    with pytest.raises(RuntimeError, match="503"):
        adzuna.fetch_query("de", "q", 1, 14, "id", "k", session=Session())
    assert len(calls) == 3
