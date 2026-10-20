import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from durable_queue import claim, enqueue, finish, queue_status, recover_all_running, recover_expired


class DurableQueueAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def test_priority_and_multiple_projects(self):
        enqueue(self.db, "project-a", "research", priority=10,mode="exploration",max_seconds=30,budget_units=10)
        enqueue(self.db, "project-b", "test", priority=90,mode="exploitation",max_seconds=30,budget_units=10)
        self.assertEqual(claim(self.db)["project_id"], "project-b")
        self.assertEqual(claim(self.db)["project_id"], "project-a")

    def test_success_records_result_and_bounded_metadata(self):
        identifier=enqueue(self.db,"project-a","health_probe",objective="Vérifier le worker",max_seconds=5,budget_units=2,success_condition="probe_ok")
        task=claim(self.db); self.assertLessEqual(task["max_seconds"],3600)
        self.assertEqual(finish(self.db,identifier,True,result={"probe":"ok"})["status"],"done")
        self.assertEqual(queue_status(self.db)["done"],1)

    def test_retry_backoff_and_bounded_failure(self):
        start = datetime.now(timezone.utc) + timedelta(seconds=1)
        identifier = enqueue(self.db, "project-a", "test", max_attempts=2)
        first = claim(self.db, at=start)
        self.assertEqual(finish(self.db, first["id"], False, "temporary", at=start)["status"], "retry")
        self.assertIsNone(claim(self.db, at=start + timedelta(seconds=1)))
        second = claim(self.db, at=start + timedelta(seconds=3))
        self.assertEqual(second["id"], identifier)
        self.assertEqual(finish(self.db, identifier, False, "permanent", at=start + timedelta(seconds=3))["status"], "failed")

    def test_restart_recovers_expired_lease_without_duplication(self):
        start = datetime.now(timezone.utc) + timedelta(seconds=1)
        identifier = enqueue(self.db, "project-a", "build")
        claim(self.db, lease_seconds=5, at=start)
        dump = "\n".join(self.db.iterdump())
        reopened = sqlite3.connect(":memory:"); reopened.executescript(dump)
        self.assertEqual(recover_expired(reopened, start + timedelta(seconds=6)), 1)
        recovered = claim(reopened, at=start + timedelta(seconds=6))
        self.assertEqual(recovered["id"], identifier)
        self.assertEqual(reopened.execute("SELECT COUNT(*) FROM autonomous_tasks").fetchone()[0], 1)

    def test_service_restart_recovers_any_abandoned_running_task(self):
        identifier = enqueue(self.db, "project-crash", "sleep_probe", {"seconds": 5})
        self.assertEqual(claim(self.db, lease_seconds=300)["id"], identifier)
        self.assertEqual(recover_all_running(self.db), 1)
        self.assertEqual(claim(self.db)["id"], identifier)


if __name__ == "__main__":
    unittest.main()
