import sqlite3
import unittest

from opportunity_engine import generate_opportunities, init_schema, select_opportunity


class OpportunityEngineAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        init_schema(self.db)
        self.created = []

    def create_project(self, candidate):
        project_id = "project-" + str(len(self.created) + 1)
        self.created.append((project_id, candidate["name"]))
        return project_id

    def test_full_scenario_evaluates_selects_and_starts_project(self):
        candidates = generate_opportunities({"lessons":["Les synthèses locales sont utiles"]})
        result = select_opportunity(self.db, candidates, self.create_project)
        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.created[0][1], "SignalDesk")
        self.assertIn("critères qualitatifs validés", result["rationale"])
        self.assertIn("alternatives rejetées", result["rationale"])
        rejected = self.db.execute("SELECT status FROM opportunities WHERE name='PublicViral'").fetchone()[0]
        self.assertEqual(rejected, "rejected")
        self.assertEqual(self.db.execute("SELECT status FROM opportunity_runs").fetchone()[0], "selected")

    def test_persists_across_reopen_dump(self):
        select_opportunity(self.db, generate_opportunities(), self.create_project)
        dump = "\n".join(self.db.iterdump())
        reopened = sqlite3.connect(":memory:")
        reopened.executescript(dump)
        self.assertEqual(reopened.execute("SELECT COUNT(*) FROM opportunities WHERE status='selected'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
