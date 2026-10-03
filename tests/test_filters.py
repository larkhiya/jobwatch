import pytest

from jobwatch.filters import KeywordFilter
from jobwatch.parse import Job, parse_jobs

from .conftest import load_fixture, make_config


def job(title: str, snippet: str = "", tags: tuple[str, ...] = ()) -> Job:
    return Job(id="1", title=title, url="u", posted=None, salary=None, snippet=snippet, job_type=None, tags=tags)


@pytest.fixture
def default_filter(tmp_path) -> KeywordFilter:
    return make_config(tmp_path).filter


@pytest.mark.parametrize(
    "title",
    [
        "Senior React Developer",
        "REACT engineer",
        "Full-Stack Engineer",
        "Fullstack Engineer",
        "Full Stack Engineer",
        "Front-End Specialist",
        "Backend (Node) engineer",
        "Laravel expert",
        "Hiring Developers",  # plural
        "Python automation",
        "WordPress Developer",
        "Software Engineer II",
    ],
)
def test_developer_titles_match(default_filter, title):
    assert default_filter.matched_keyword(job(title))


@pytest.mark.parametrize(
    "title",
    [
        "Reactive customer support",  # "react" must be a whole word
        "Virtual Assistant",
        "Business Development Manager",  # "development" is not "developer"
        "Real estate cold caller",
    ],
)
def test_non_developer_titles_do_not_match(default_filter, title):
    assert default_filter.matched_keyword(job(title)) is None


def test_snippet_and_tags_are_searched_too(default_filter):
    assert default_filter.matched_keyword(job("Tech hire", snippet="You will build APIs in Python."))
    assert default_filter.matched_keyword(job("Tech hire", tags=("React",)))


def test_exclude_beats_include(default_filter):
    assert default_filter.matched_keyword(job("Web Developer - commission only")) is None
    assert default_filter.matched_keyword(job("Developer", snippet="This is an UNPAID internship")) is None
    assert default_filter.matched_keyword(job("Web Developer (Commission-Only)")) is None


def test_returns_the_first_matching_keyword():
    flt = KeywordFilter(include=["python", "developer"])
    assert flt.matched_keyword(job("Python Developer")) == "python"


def test_symbols_in_keywords_work():
    flt = KeywordFilter(include=["c++", "node.js"])
    assert flt.matched_keyword(job("C++ game programmer"))
    assert flt.matched_keyword(job("Node.js API work"))
    assert flt.matched_keyword(job("Nodexjs")) is None  # the dot is literal, not "any character"


def test_latest_jobs_fixture_has_no_developer_jobs(default_filter):
    # Captured around midnight PHT: all VA/marketing/editing roles.
    assert default_filter.apply(parse_jobs(load_fixture("jobsearch_latest.html"))) == []


def test_developer_search_fixture_is_filtered_sensibly(default_filter):
    jobs = parse_jobs(load_fixture("jobsearch_developer.html"))
    kept = {job.id for job in default_filter.apply(jobs)}
    assert len(kept) == 17
    assert {"1742846", "1742338", "1742498"} <= kept  # Senior WordPress / Full Stack / Salesforce Developer
    assert not {"1741650", "1742325"} & kept  # Business Development Specialist / QA Engineer
