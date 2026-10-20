import json
import pathlib
import sqlite3
import unittest

from n8n_bridge import WORKFLOWS, invoke


class N8nBridgeAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def test_three_allowlisted_workflows(self):
        transformed = invoke(self.db, "AtlasDataTransform001", {"rows":[{" Name ":"Atlas"}]})
        report = invoke(self.db, "AtlasLocalReport001", {"title":"Santé", "metrics":{"projects":3}})
        task = invoke(self.db, "AtlasTaskProcess001", {"task":{"id":"t-1", "next_action":"test"}})
        self.assertEqual(transformed["rows"], [{"name":"Atlas"}])
        self.assertIn("projects: 3", report["report"])
        self.assertEqual(task["status"], "processed")
        self.assertTrue(all(item["external_actions"] is False for item in (transformed, report, task)))

    def test_invalid_and_unknown_requests_are_blocked_and_audited(self):
        with self.assertRaisesRegex(ValueError, "ALLOWLISTED"):
            invoke(self.db, "DangerousWorkflow", {})
        with self.assertRaisesRegex(ValueError, "INVALID_ROWS"):
            invoke(self.db, "AtlasDataTransform001", {"rows":"bad"})
        self.assertEqual(self.db.execute("SELECT status FROM workflow_runs").fetchone()[0], "failed")

    def test_workflows_contain_no_credentials_and_survive_database_reopen(self):
        root = pathlib.Path(__file__).with_name("n8n-workflows")
        files = list(root.glob("*.json"))
        self.assertEqual(len(files), 3)
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn(data["id"], WORKFLOWS)
            def keys(value):
                if isinstance(value, dict):
                    return set(value) | set().union(*(keys(item) for item in value.values()))
                if isinstance(value, list):
                    return set().union(*(keys(item) for item in value)) if value else set()
                return set()
            self.assertNotIn("credentials", {key.casefold() for key in keys(data)})
        invoke(self.db, "AtlasLocalReport001", {"metrics":{"ok":True}})
        dump = "\n".join(self.db.iterdump())
        reopened = sqlite3.connect(":memory:"); reopened.executescript(dump)
        self.assertEqual(reopened.execute("SELECT status FROM workflow_runs").fetchone()[0], "success")


if __name__ == "__main__":
    unittest.main()
