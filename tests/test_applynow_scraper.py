import unittest

from scrapers.applynow_scraper import ApplyNowScraper


class StubApplyNowScraper(ApplyNowScraper):
    def __init__(self):
        super().__init__()
        self.calls = []

    def _fetch_json(self, endpoint, params):
        self.calls.append((endpoint, params))
        if endpoint == "tags" and "slug" in params:
            return [{"id": {"zimbabwe": 1, "remote": 2}[params["slug"]]}]
        if endpoint == "posts":
            if params["tags"] == 1:
                return [self.job_post, self.scholarship_post]
            return [self.job_post]
        if endpoint == "tags":
            return [{"id": 10, "name": "Remote"}]
        if endpoint == "categories":
            return [{"id": 20, "name": "Jobs"}]
        return []

    job_post = {
        "date": "2026-09-08T10:47:51",
        "link": "https://applynow.co.zw/2026/09/08/acme-developer/",
        "tags": [10],
        "categories": [20],
        "title": {"rendered": "Acme Is Hiring: Junior Software Developer"},
        "content": {"rendered": """
            <p><strong>Job Title:</strong> Junior Software Developer<br>
            <strong>Job Location:</strong> Remote<br>
            <strong>Closing Date:</strong> 12 September 2026<br>
            <strong>Contract:</strong> Full-time<br>
            <strong>Salary:</strong> USD 1,200 per month</p>
            <h2>Requirements</h2><p>Python and Django experience.</p>
            <h2>How to Apply</h2><p><a href="https://jobs.example.com/apply">Apply for this role</a></p>
        """},
    }
    scholarship_post = {
        "date": "2026-09-08T10:47:51",
        "link": "https://applynow.co.zw/2026/09/08/scholarship/",
        "tags": [10],
        "categories": [20],
        "title": {"rendered": "Software Engineering Scholarship"},
        "content": {"rendered": "<p>Job Title: Student</p>"},
    }


class ApplyNowScraperTests(unittest.TestCase):
    def test_merges_feeds_marks_remote_and_extracts_fields(self):
        scraper = StubApplyNowScraper()

        jobs = scraper.scrape_jobs(max_pages=1, delay=0)

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["site"], "applynow")
        self.assertEqual(job["title"], "Junior Software Developer")
        self.assertEqual(job["company"], "Acme")
        self.assertEqual(job["location"], "Remote")
        self.assertEqual(job["remote"], "Remote")
        self.assertEqual(job["job_type"], "Full-time")
        self.assertEqual(job["compensation"], "USD 1,200 per month")
        self.assertEqual(job["date_posted"], "2026-09-08")
        self.assertEqual(job["expires"], "2026-09-12")
        self.assertIn("Apply for this role (https://jobs.example.com/apply)", job["apply_instructions"])
        self.assertIn("Python and Django experience.", job["description"])

    def test_existing_urls_and_max_jobs_are_honoured(self):
        scraper = StubApplyNowScraper()
        existing = {"https://applynow.co.zw/2026/09/08/acme-developer/"}

        self.assertEqual(scraper.scrape_jobs(delay=0, existing_urls=existing), [])
        self.assertEqual(len(scraper.scrape_jobs(delay=0, max_jobs=1)), 1)

    def test_max_pages_is_applied_to_each_feed(self):
        scraper = StubApplyNowScraper()

        scraper.scrape_jobs(max_pages=2, delay=0)

        pages = [params["page"] for endpoint, params in scraper.calls if endpoint == "posts"]
        self.assertEqual(pages, [1, 2, 1, 2])

    def test_non_job_opportunity_types_are_excluded(self):
        scraper = StubApplyNowScraper()

        for kind in ("Scholarship", "Grant", "Fellowship", "Course", "Contest"):
            with self.subTest(kind=kind):
                self.assertFalse(scraper._is_eligible(f"Software {kind}", "", ""))

    def test_missing_optional_labels_do_not_drop_an_eligible_job(self):
        scraper = StubApplyNowScraper()
        post = {
            "date": "2026-09-08T10:47:51",
            "link": "https://applynow.co.zw/2026/09/08/qa-engineer/",
            "tags": [],
            "categories": [],
            "title": {"rendered": "Example Co is hiring a QA Engineer"},
            "content": {"rendered": "<p>We are hiring a QA engineer. <a href='https://example.com/apply'>Apply now</a></p>"},
        }

        job = scraper._to_job(post, remote_from_feed=False, delay=0)

        self.assertEqual(job["title"], "Example Co is hiring a QA Engineer")
        self.assertIsNone(job["location"])
        self.assertIsNone(job["expires"])
        self.assertIn("https://example.com/apply", job["apply_instructions"])


if __name__ == "__main__":
    unittest.main()
