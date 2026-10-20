import json
import sqlite3
import unittest

from decision import decide
from memory_engine import FAILURE_DIMENSIONS, classify_failure, record_experience, relevant_cross_project


class MemoryDecisionAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE experiences(id TEXT PRIMARY KEY,project_id TEXT,created TEXT,payload TEXT)")

    def tearDown(self):
        self.db.close()

    def test_all_five_decisions_have_reason_and_next_action(self):
        cases = {
            "CONTINUE": {"source":"synthetic","technical_pass":True,"tests":1,"visitors":0},
            "MODIFIE": {"source":"real","technical_pass":False,"tests":5,"visitors":500},
            "PIVOTE": {"source":"real","technical_pass":True,"tests":5,"visitors":500,"conversions":2,"problem_confirmed":True},
            "ABANDONNE": {"source":"real","technical_pass":True,"tests":5,"visitors":500,"conversions":2,"distinct_hypotheses":3,"negative_feedback_confirmed":True},
            "SCALE": {"source":"real","technical_pass":True,"tests":5,"visitors":500,"conversions":40,"repeatable_runs":3,"unit_economics_positive":True},
        }
        for expected, metrics in cases.items():
            result = decide(metrics)
            self.assertEqual(result["choice"], expected)
            self.assertTrue(result["reason"] and result["next_action"])

    def test_failure_dimensions_are_bounded(self):
        examples = ["bug critique", "parcours UX confus", "prix trop cher", "message imprécis", "mauvais segment", "canal email", "distribution faible", "trafic insuffisant", "aucune demande"]
        self.assertEqual({classify_failure(value) for value in examples}, set(FAILURE_DIMENSIONS))

    def test_new_project_reuses_only_relevant_other_project_memory(self):
        record_experience(self.db, "crm-old", {"application_type":"crm", "lessons":["Clarifier le segment prospect et le pipeline"], "failed":["mauvais segment"], "estimated_cost_eur":0, "estimated_minutes":3})
        record_experience(self.db, "music-old", {"application_type":"music-library", "lessons":["Améliorer le lecteur musical"], "failed":["bug lecteur"]})
        self.db.commit()
        matches = relevant_cross_project(self.db, "crm-new", {"application_type":"crm", "entities":["prospect"], "features":["pipeline"], "target_user":"segment commercial"})
        self.assertEqual([item["project_id"] for item in matches], ["crm-old"])
        self.assertTrue(matches[0]["matched_terms"])

    def test_memory_survives_reopen(self):
        script = "\n".join(self.db.iterdump())
        reopened = sqlite3.connect(":memory:")
        reopened.executescript(script)
        self.assertEqual(reopened.execute("SELECT COUNT(*) FROM experiences").fetchone()[0], self.db.execute("SELECT COUNT(*) FROM experiences").fetchone()[0])
        reopened.close()


if __name__ == "__main__":
    unittest.main()
