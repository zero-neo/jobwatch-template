import pytest

from jobwatch.config import ConfigError, Filters, load_companies, load_filters
from jobwatch.filters import JobFilter
from jobwatch.models import Company, Job
from jobwatch.pipeline import collect
from jobwatch.storage import Store


def mk(i, title="Python Dev"):
    return Job("greenhouse", str(i), title, "Acme", "Berlin", "http://x", None, "")


def test_dedup_across_runs(tmp_path):
    store = Store(str(tmp_path / "t.sqlite"))
    assert len(store.add_new([mk(1), mk(2), mk(1)])) == 2
    assert store.add_new([mk(1), mk(2)]) == []
    assert [j.external_id for j in store.add_new([mk(3)])] == ["3"]


def test_pending_and_mark(tmp_path):
    store = Store(str(tmp_path / "t.sqlite"))
    store.add_new([mk(1), mk(2)])
    pending = store.pending("synced")
    assert len(pending) == 2
    store.mark("synced", pending[:1])
    assert len(store.pending("synced")) == 1
    assert len(store.pending("notified")) == 2
    with pytest.raises(ValueError):
        store.pending("title; DROP TABLE jobs")


def test_one_failing_company_does_not_stop_run():
    good, bad = Company("Good", "greenhouse", "g"), Company("Bad", "greenhouse", "b")

    def fetch(company):
        if company.name == "Bad":
            raise RuntimeError("404")
        return [mk(1)]

    f = JobFilter(Filters(title_include=["python"], locations=["berlin"]))
    matched, errors = collect([bad, good], f, fetchers={"greenhouse": fetch})
    assert len(matched) == 1 and len(errors) == 1 and "Bad" in errors[0]


def test_config_validation(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("title_includ: [python]\n")  # typo
    with pytest.raises(ConfigError):
        load_filters(p)
    p.write_text("locations: [Berlin]\n")  # nothing to match on
    with pytest.raises(ConfigError):
        load_filters(p)
    q = tmp_path / "co.yaml"
    q.write_text("companies:\n  - {name: X, ats: nonsense, slug: x}\n")
    with pytest.raises(ConfigError):
        load_companies(q)


def test_shipped_configs_load():
    assert load_filters("config.yaml").title_include
    assert load_companies("companies.yaml")
