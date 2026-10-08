import pytest

from jobwatch import sheets
from jobwatch.models import Job
from jobwatch.storage import Store


def mk(i, title="Python Dev"):
    return Job("greenhouse", str(i), title, "Acme", "Berlin", f"http://x/{i}",
               "2026-10-01T10:00:00-04:00", "")


class FakeWorksheet:
    def __init__(self, header=None, fail=False):
        self.rows = [header] if header else []
        self.fail = fail
        self.options = None

    def row_values(self, n):
        return self.rows[0] if self.rows else []

    def append_rows(self, rows, value_input_option):
        if self.fail:
            raise RuntimeError("quota exceeded")
        self.options = value_input_option
        self.rows.extend(rows)


def test_first_sync_writes_header_then_rows(tmp_path):
    store = Store(str(tmp_path / "t.sqlite"))
    store.add_new([mk(1), mk(2)])
    ws = FakeWorksheet()
    assert sheets.sync(store, ws, today="2026-10-08") == 2
    assert ws.rows[0] == sheets.HEADERS
    assert ws.rows[1] == ["2026-10-08", "Acme", "Python Dev", "Berlin",
                          "2026-10-01", "http://x/1", "", ""]
    assert ws.options == "RAW"
    assert store.pending("synced") == []


def test_existing_header_not_repeated_and_second_sync_adds_nothing(tmp_path):
    store = Store(str(tmp_path / "t.sqlite"))
    store.add_new([mk(1)])
    ws = FakeWorksheet(header=sheets.HEADERS)
    sheets.sync(store, ws, today="d")
    assert len(ws.rows) == 2
    assert sheets.sync(store, ws, today="d") == 0
    assert len(ws.rows) == 2


def test_failed_append_leaves_jobs_pending(tmp_path):
    store = Store(str(tmp_path / "t.sqlite"))
    store.add_new([mk(1)])
    with pytest.raises(RuntimeError):
        sheets.sync(store, FakeWorksheet(fail=True), today="d")
    assert len(store.pending("synced")) == 1


def test_not_configured_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("JOBWATCH_SHEET_ID", raising=False)
    store = Store(str(tmp_path / "t.sqlite"))
    assert sheets.sync_from_env(store) is None


def test_credentials_from_inline_json_or_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"a": 1}')
    assert sheets._credentials() == {"a": 1}
    key = tmp_path / "key.json"
    key.write_text('{"b": 2}')
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(key))
    assert sheets._credentials() == {"b": 2}
