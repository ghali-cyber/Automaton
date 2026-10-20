import sqlite3
import unittest

from monitoring_engine import record_sample, status


class MonitoringAcceptance(unittest.TestCase):
    def test_incident_is_detected_persisted_and_resolved(self):
        db = sqlite3.connect(":memory:")
        first = record_sample(db, "ollama", False, 2500, {"error":"timeout simulé"})
        self.assertIsNotNone(first["incident_id"])
        self.assertEqual(status(db)["open_incidents"], 1)
        record_sample(db, "ollama", True, 42, {"model":"qwen2.5:1.5b"})
        report = status(db, {"cpu_load":[0.2,0.1,0.1], "disk":{"available":1000}})
        self.assertEqual(report["open_incidents"], 0)
        self.assertEqual(report["services"]["ollama"]["status"], "healthy")
        self.assertEqual(report["incidents"][0]["status"], "resolved")

    def test_history_survives_restart(self):
        db = sqlite3.connect(":memory:")
        record_sample(db, "atlas-control", True, 8)
        dump = "\n".join(db.iterdump())
        reopened = sqlite3.connect(":memory:"); reopened.executescript(dump)
        self.assertEqual(status(reopened)["services"]["atlas-control"]["latency_ms"], 8)


if __name__ == "__main__":
    unittest.main()
