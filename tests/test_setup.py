from jobwatch import sheets
from jobwatch.__main__ import init_files, main


def test_init_creates_files_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("config.example.yaml", "companies.example.yaml", ".env.example"):
        (tmp_path / name).write_text("template")
    init_files()
    assert (tmp_path / "config.yaml").read_text() == "template"
    (tmp_path / "config.yaml").write_text("mine")
    init_files()
    assert (tmp_path / "config.yaml").read_text() == "mine"


def test_check_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("JOBWATCH_SHEET_ID", raising=False)
    assert "not configured" in sheets.check_connection()


def test_check_failure_names_the_email_to_share_with(monkeypatch):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"client_email": "bot@x.iam.gserviceaccount.com"}')
    monkeypatch.setenv("JOBWATCH_SHEET_ID", "abc")

    def boom(*a, **k):
        raise RuntimeError("not found")

    monkeypatch.setattr(sheets, "open_worksheet", boom)
    message = sheets.check_connection()
    assert "bot@x.iam.gserviceaccount.com" in message and "shared" in message


def test_main_check_runs_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("JOBWATCH_SHEET_ID", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("title_include: [python]\n")
    (tmp_path / "companies.yaml").write_text(
        "companies:\n  - {name: A, ats: lever, slug: a}\n  - {name: B, ats: greenhouse, slug: b}\n")
    assert main(["--check"]) == 0
    assert "Config OK: 2 companies (greenhouse, lever)" in capsys.readouterr().out
