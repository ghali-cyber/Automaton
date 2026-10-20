import sqlite3
import unittest

from financial_simulation import configure, record, set_budget, summary


class FinancialSimulationAcceptance(unittest.TestCase):
    def test_project_and_global_metrics_are_strictly_simulated(self):
        db = sqlite3.connect(":memory:")
        configure(db, global_budget_cents=300000, monthly_budget_cents=200000, max_expense_cents=50000,
                  min_reserve_cents=50000, allowed_categories=("acquisition", "hosting"), blocked_categories=("crypto",))
        set_budget(db, "project-a", 100000)
        record(db, "project-a", "cost", 25000, "acquisition", "Scénario fictif")
        record(db, "project-a", "revenue", 40000, "subscription", "Revenu fictif")
        set_budget(db, "project-b", 50000)
        record(db, "project-b", "cost", 10000, "hosting", "Hébergement simulé")
        report = summary(db)
        self.assertEqual(report["label"], "SIMULATION — AUCUN ARGENT RÉEL")
        self.assertFalse(report["payment_capability"])
        self.assertEqual(report["projects"]["project-a"]["roi_percent"], 60.0)
        self.assertEqual(report["totals"]["remaining_cents"], 115000)
        self.assertTrue(all(project["simulation"] for project in report["projects"].values()))

    def test_invalid_real_world_kind_is_rejected_and_state_persists(self):
        db = sqlite3.connect(":memory:")
        with self.assertRaisesRegex(ValueError, "INVALID"):
            record(db, "project-a", "payment", 100, "card", "forbidden")
        configure(db, global_budget_cents=10000, monthly_budget_cents=8000, max_expense_cents=3000,
                  min_reserve_cents=2000, allowed_categories=("test",), blocked_categories=("crypto",))
        set_budget(db, "project-a", 5000); record(db, "project-a", "cost", 1000, "test", "simulation")
        dump = "\n".join(db.iterdump())
        reopened = sqlite3.connect(":memory:"); reopened.executescript(dump)
        self.assertEqual(summary(reopened)["projects"]["project-a"]["remaining_cents"], 4000)

    def test_every_spending_rule_rejects_and_is_audited(self):
        cases = [
            ("crypto", 100, "CATEGORY_BLOCKED", 10000, 10000, 5000, 0, 10000),
            ("unknown", 100, "CATEGORY_NOT_ALLOWED", 10000, 10000, 5000, 0, 10000),
            ("hosting", 5001, "MAX_EXPENSE_EXCEEDED", 10000, 10000, 5000, 0, 10000),
            ("hosting", 4001, "PROJECT_BUDGET_EXCEEDED", 10000, 10000, 5000, 0, 4000),
            ("hosting", 4001, "MONTHLY_BUDGET_EXCEEDED", 10000, 4000, 5000, 0, 10000),
            ("hosting", 3001, "MINIMUM_RESERVE_VIOLATED", 5000, 10000, 5000, 2000, 10000),
        ]
        for category, amount, reason, global_cap, monthly, maximum, reserve, project_cap in cases:
            with self.subTest(reason=reason):
                db = sqlite3.connect(":memory:")
                configure(db, global_budget_cents=global_cap, monthly_budget_cents=monthly,
                          max_expense_cents=maximum, min_reserve_cents=reserve,
                          allowed_categories=("hosting",), blocked_categories=("crypto",))
                set_budget(db, "project-a", project_cap)
                with self.assertRaisesRegex(ValueError, reason):
                    record(db, "project-a", "cost", amount, category, "Scénario rejeté")
                report = summary(db)
                self.assertEqual(report["rejections"][0]["reason"], reason)
                self.assertEqual(report["totals"]["costs_cents"], 0)


if __name__ == "__main__":
    unittest.main()
