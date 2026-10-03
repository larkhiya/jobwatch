from datetime import datetime, timezone

from jobwatch.parse import parse_jobs

from .conftest import load_fixture


def jobs_by_id():
    return {job.id: job for job in parse_jobs(load_fixture("jobsearch_latest.html"))}


def test_parses_all_30_cards_with_unique_numeric_ids():
    jobs = parse_jobs(load_fixture("jobsearch_latest.html"))
    assert len(jobs) == 30
    assert len({job.id for job in jobs}) == 30
    assert all(job.id.isdigit() for job in jobs)


def test_keeps_page_order_newest_first():
    jobs = parse_jobs(load_fixture("jobsearch_latest.html"))
    posted = [job.posted for job in jobs]
    assert posted == sorted(posted, reverse=True)


def test_extracts_all_fields_of_a_card():
    job = jobs_by_id()["1463731"]
    assert job.title == "Digital Marketing - Editor"  # badge text removed from title
    assert job.job_type == "Full Time"
    assert job.url == "https://www.onlinejobs.ph/jobseekers/job/digital-marketing-editor-1463731"
    assert job.posted == datetime(2026, 10, 3, 16, 1, 40, tzinfo=timezone.utc)
    assert job.salary == "$5 to $10 an hour"
    assert job.snippet.startswith("We’re searching for a creative and skilled Graphic Designer")
    assert job.snippet.endswith("…")
    assert "See More" not in job.snippet
    assert job.tags == ()  # this card has an empty category badge


def test_card_with_employer_logo_and_unicode_salary():
    job = jobs_by_id()["1695237"]
    assert job.title == "Executive Assistant"
    assert job.salary == "PHP ?42,000 – ?46,000 per month"
    assert job.tags == ("Executive Assistance",)


def test_empty_salary_becomes_none():
    assert jobs_by_id()["1627367"].salary is None


def test_search_text_includes_title_snippet_and_tags():
    job = jobs_by_id()["1695237"]
    assert "Executive Assistant" in job.search_text
    assert "Scaledforce" in job.search_text
    assert "Executive Assistance" in job.search_text


def test_page_without_cards_returns_empty_list():
    assert parse_jobs(load_fixture("jobsearch_empty.html")) == []


def test_duplicate_cards_are_returned_once():
    card = '<a href="/jobseekers/job/web-developer-123"><div class="jobpost-cat-box"><h4>Web Developer</h4></div></a>'
    jobs = parse_jobs(card * 2)
    assert [job.id for job in jobs] == ["123"]
    assert jobs[0].posted is None and jobs[0].salary is None and jobs[0].snippet == ""


def test_card_without_numeric_id_is_skipped():
    card = '<a href="/jobseekers/job/no-number-here"><div class="jobpost-cat-box"><h4>Developer</h4></div></a>'
    assert parse_jobs(card) == []
