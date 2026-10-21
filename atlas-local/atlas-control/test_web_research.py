import sqlite3
import unittest

import web_research


class FakeBroker:
    def __init__(self):
        self.opens = 0

    def __call__(self, action, **args):
        if action == "web_search":
            slug = args["query"].split('"')[1].casefold()
            return {"provider": "test-search", "retrieved_at": "2026-10-20T00:00:00+00:00", "results": [
                {"title": slug + " official pricing", "url": f"https://{slug}.example.com/pricing", "date": "2026-10-01"},
                {"title": slug + " market report", "url": f"https://research.example.org/{slug}", "date": "2026-09-01"},
                {"title": "duplicate", "url": f"https://{slug}.example.com/pricing?utm_source=x", "date": ""},
            ]}
        self.opens += 1
        url = args["url"]
        domain = url.split("/")[2]
        if domain == "research.example.org":
            title="Independent market report";excerpt="Independent analysis reports demand growth, adoption evidence and an estimated market price of €29 for small teams."
        else:
            title="Official product pricing";excerpt="The vendor publishes a $19 monthly plan, product capabilities and limitations for public comparison."
        return {"url": url, "domain": domain, "title": title, "date": "2026-10-01", "retrieved_at": "2026-10-20T00:00:01+00:00", "excerpt": excerpt, "source_type": "product_or_pricing"}


class WebResearchAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.candidates = [
            {"name": name, "problem": "A sufficiently specific public problem for testing", "target_user": "Small public teams", "hypothesis": "A local tool saves time", "value_potential": "moyen", "competition": "moyenne", "differentiation": "local", "evidence": {"estimated_cost_eur": 0}}
            for name in ("Alpha", "Beta", "Gamma")
        ]

    def test_three_opportunities_sources_quality_and_persistence(self):
        result = web_research.research_candidates(self.db, self.candidates, FakeBroker())
        self.assertEqual(result["status"], "researched")
        self.assertEqual(result["source_count"], 6)
        self.assertEqual(len(result["candidates"]), 3)
        self.assertTrue(all(c["confidence"] == "medium" for c in result["candidates"]))
        self.assertTrue(all(c["evidence"]["price_observations"] for c in result["candidates"]))
        dump = "\n".join(self.db.iterdump())
        reopened = sqlite3.connect(":memory:"); reopened.executescript(dump)
        self.assertEqual(reopened.execute("SELECT COUNT(*) FROM web_sources WHERE status='stored'").fetchone()[0], 6)

    def test_url_content_and_entity_deduplication(self):
        web_research.init_schema(self.db)
        source = {"url": "https://example.com/product?utm_source=x", "domain": "example.com", "title": "Acme Product Pricing", "excerpt": "Same useful market content " * 20}
        first = web_research.store_source(self.db, "run", "Alpha", source)
        second = web_research.store_source(self.db, "run", "Alpha", {**source, "url": "https://example.com/product?utm_campaign=y"})
        third = web_research.store_source(self.db, "run", "Alpha", {**source, "url": "https://example.com/another"})
        self.assertEqual(first["status"], "stored")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(third["status"], "duplicate")

    def test_each_opportunity_requires_two_independent_domains(self):
        class SparseBroker(FakeBroker):
            def __call__(self, action, **args):
                if action == "web_search":
                    slug = args["query"].split('"')[1].casefold()
                    return {"provider": "test-search", "retrieved_at": "2026-10-20T00:00:00+00:00", "results": [
                        {"title": slug + " single source", "url": f"https://{slug}.example.com/report", "date": "2026-10-01"},
                    ]}
                return super().__call__(action, **args)

        result = web_research.research_candidates(self.db, self.candidates, SparseBroker())
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["complete_candidates"], 0)


if __name__ == "__main__":
    unittest.main()
