from jobwatch.config import Filters
from jobwatch.filters import JobFilter
from jobwatch.models import Job


def job(title="Python Developer", location="Berlin, Germany", description=""):
    return Job("greenhouse", "1", title, "Acme", location, "http://x", None, description)


def make(**kw):
    base = dict(title_include=["python", "software engineer*"], description_include=[],
                title_exclude=["intern*"], locations=["Germany", "Remote"])
    base.update(kw)
    return JobFilter(Filters(**base))


def test_whole_word_match():
    f = make(title_include=["ml"])
    assert f.matches(job("ML Engineer"))
    assert not f.matches(job("HTML Designer"))


def test_wildcard_prefix():
    f = make()
    assert f.matches(job("Software Engineering Lead"))
    assert f.matches(job("Software Engineers"))


def test_exclude_wins():
    assert not make().matches(job("Python Intern"))
    assert not make().matches(job("Python Internship"))


def test_location_filter():
    f = make()
    assert f.matches(job(location="Remote - EU"))
    assert not f.matches(job(location="Austin, USA"))


def test_empty_locations_means_no_filter():
    assert make(locations=[]).matches(job(location="Austin, USA"))


def test_description_route():
    f = make(title_include=["zzz"], description_include=["zebrafish"])
    assert f.matches(job("Scientist", description="We study zebrafish behaviour"))
    assert not f.matches(job("Scientist", description="We study mice"))


def test_special_characters_in_terms():
    f = make(title_include=["c++"])
    assert f.matches(job("C++ Developer"))


def test_location_exclude_drops_job():
    f = make(locations=["Remote"], location_exclude=["US", "United States"])
    assert f.matches(job(location="Remote - Germany"))
    assert not f.matches(job(location="Remote from the US"))
    assert not f.matches(job(location="Remote, United States"))


def test_locations_are_whole_word():
    # "US" must not match inside "Austria"; "UK" must not match "Ukraine"
    f = make(locations=["UK"], location_exclude=["US"])
    assert f.matches(job(location="London, UK"))
    assert not f.matches(job(location="Kyiv, Ukraine"))
    assert make(locations=["Austria"], location_exclude=["US"]).matches(job(location="Vienna, Austria"))
