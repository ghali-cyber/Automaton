import sqlite3
import unittest
from pathlib import Path

from security_engine import BLOCKED, SAFE_LOCAL, authorize


class SecurityPolicyAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def test_safe_local_actions_are_allowed_and_audited(self):
        for action in SAFE_LOCAL:
            result = authorize(self.db, action, context={"project_id":"p-local"})
            self.assertTrue(result["allowed"])
            self.assertEqual(result["reason"], "LOCAL_ALLOWLIST")

    def test_external_money_crypto_and_irreversible_actions_are_blocked(self):
        for action, alternative in BLOCKED.items():
            result = authorize(self.db, action)
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason"], "BLOCKED_BY_POLICY")
            self.assertEqual(result["safe_alternative"], alternative)

    def test_unknown_action_is_denied_and_audit_survives_restart(self):
        authorize(self.db, "invented_tool", actor="test-agent")
        dump = "\n".join(self.db.iterdump())
        reopened = sqlite3.connect(":memory:"); reopened.executescript(dump)
        row = reopened.execute("SELECT allowed,reason,actor FROM policy_audit").fetchone()
        self.assertEqual(row, (0, "UNKNOWN_ACTION_DENIED", "test-agent"))

    def test_service_hardening_is_deny_by_default(self):
        unit = Path(__file__).with_name("systemd").joinpath("atlas-control.service").read_text()
        for directive in ("NoNewPrivileges=true", "ProtectSystem=strict", "ProtectHome=true", "CapabilityBoundingSet=", "UMask=0077"):
            self.assertIn(directive, unit)


if __name__ == "__main__":
    unittest.main()
