import sqlite3

from jobwatch.__main__ import main
from jobwatch.config import ConfigError, Filters, load_filters
from jobwatch.dedupe import dedupe, listing_key
from jobwatch.filters import JobFilter
from jobwatch.language import looks_english
from jobwatch.models import Job
from jobwatch.storage import Store
import pytest

GERMAN = ("Wir suchen eine Data Scientist (m/w/d) für unser Team in Berlin. Sie verfügen über "
          "Erfahrung mit Python und Machine Learning. Ihre Aufgaben: Entwicklung von Modellen mit "
          "unseren Daten und die Zusammenarbeit mit dem Team.")
DUTCH = ("Wij zoeken een Data Scientist voor ons team. Je werkt met Python en bouwt modellen voor "
         "onze klanten. Ervaring met machine learning is een pré en je hebt een hbo of wo opleiding.")
FRENCH = ("Nous recherchons un Data Scientist pour rejoindre notre équipe. Vous travaillerez avec "
          "Python et développerez des modèles pour nos clients dans le secteur bancaire.")
ENGLISH = ("We are looking for a Data Scientist to join our team. You will work with Python and "
           "build models for the business. Experience with machine learning is required.")


def mk(i, title="Data Scientist", company="Acme", location="Berlin, Germany", description=""):
    return Job("adzuna", str(i), title, company, location, f"http://x/{i}", None, description)


def test_language_heuristic():
    assert looks_english(ENGLISH)
    for text in (GERMAN, DUTCH, FRENCH):
        assert not looks_english(text)


def test_unclear_or_short_text_is_kept():
    assert looks_english("")
    assert looks_english("Data Scientist (m/w/d) im KI-Kompetenzzentrum")
    assert looks_english("Senior Machine Learning Engineer")


def test_german_company_with_english_ad_is_kept():
    assert looks_english("Union Investment is hiring. You will join our data team and work with "
                         "stakeholders to build models for the business and our clients.")


def test_gender_markers_ignored_in_listing_key():
    keys = {listing_key("Acme GmbH", t) for t in
            ("Data Scientist (m/w/d)", "Data Scientist (w/m/d)", "Data Scientist (all genders)",
             "data scientist (f|m|d)", "Data  Scientist")}
    assert len(keys) == 1
    assert listing_key("Acme", "Data Scientist") != listing_key("Acme", "Senior Data Scientist")


def test_dedupe_keeps_first_and_order():
    jobs = [mk(1, company="Lieferando", location="Mitte, Berlin"), mk(2, company="Lieferando", location="Neukölln, Berlin"),
            mk(3, company="Sia")]
    assert [j.external_id for j in dedupe(jobs)] == ["1", "3"]


def test_company_exclude_and_english_only_in_filter():
    f = JobFilter(Filters(title_include=["data scien*"], company_exclude=["Jobgether"], english_only=True))
    assert f.matches(mk(1, description=ENGLISH))
    assert not f.matches(mk(2, company="Jobgether", description=ENGLISH))
    assert not f.matches(mk(3, description=GERMAN))
    assert f.non_english_dropped == 1  # only the German one reached the language check


def test_english_only_must_be_boolean(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("title_include: [x]\nenglish_only: yes please\n")
    with pytest.raises(ConfigError):
        load_filters(p)
    p.write_text("title_include: [x]\nenglish_only: true\ncompany_exclude: [Foo]\n")
    f = load_filters(p)
    assert f.english_only is True and f.company_exclude == ["Foo"]


def test_reposts_with_new_ids_are_dropped_across_runs(tmp_path):
    store = Store(str(tmp_path / "t.sqlite"))
    store.add_new([mk(1)])
    later = [mk(2), mk(1), mk(3, title="Data Analyst")]  # 2 is a repost of 1, 1 is the same job
    kept = store.drop_known_listings(later)
    assert [j.external_id for j in kept] == ["1", "3"]
    assert [j.external_id for j in store.add_new(kept)] == ["3"]


def test_existing_database_is_migrated_not_lost(tmp_path):
    path = str(tmp_path / "old.sqlite")
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE jobs (key TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        company TEXT NOT NULL, title TEXT NOT NULL, location TEXT NOT NULL, url TEXT NOT NULL, posted TEXT,
        first_seen TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0, notified INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("INSERT INTO jobs VALUES ('adzuna:acme:1','adzuna','1','Acme','Data Scientist (m/w/d)',"
                 "'Berlin','u',NULL,'2026-10-01T00:00:00+00:00',1,1)")
    conn.commit()
    conn.close()
    store = Store(path)
    assert store.drop_known_listings([mk(2)]) == []          # old row now counts as known
    assert [j.external_id for j in store.add_new([mk(5, title="Other")])] == ["5"]
    assert store.conn.execute("SELECT synced, notified FROM jobs WHERE key='adzuna:acme:1'").fetchone() == (1, 1)
    Store(path)  # opening twice must not fail


def test_main_merges_duplicates_and_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("jobwatch.__main__.load_dotenv", lambda *a, **k: None)
    (tmp_path / "config.yaml").write_text("title_include: [data scien*]\n")
    (tmp_path / "companies.yaml").write_text("companies: []\n")
    (tmp_path / "searches.yaml").write_text("adzuna:\n  countries: [de]\n  queries: [data]\n")
    monkeypatch.setattr("jobwatch.__main__.collect_adzuna",
                        lambda s, f: ([mk(1, company="Lieferando"), mk(2, company="Lieferando")], []))
    assert main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "1 repeat posting(s) merged." in out and "1 matching job(s)" in out


def test_skipped_listings_are_counted_once_and_listable():
    f = JobFilter(Filters(title_include=["data scien*"], english_only=True))
    german = mk(1, description=GERMAN)
    for _ in range(3):          # the same listing returned by three different queries
        f.matches(german)
    assert f.non_english_dropped == 1 and f.non_english_skipped == [german]
