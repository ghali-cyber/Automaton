import unittest
import pathlib
import sys

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'atlas-business'))
import web_gateway
import sqlite3
from security_engine import authorize


class WebGatewayPolicyAcceptance(unittest.TestCase):
    def test_safe_url_is_normalized(self):
        self.assertEqual(web_gateway.canonical_url("https://Example.com//public?q=market"), "https://example.com/public?q=market")

    def test_dangerous_urls_are_blocked_by_policy(self):
        values = [
            "http://example.com", "https://127.0.0.1", "https://example.local/public",
            "https://example.com/login", "https://example.com/download.exe",
            "https://example.com/public?token=private", "https://user:pass@example.com/public",
            "https://xn--exmple-cua.com/public", "file:///etc/passwd",
        ]
        for value in values:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "BLOCKED_BY_POLICY"):
                web_gateway.canonical_url(value)

    def test_sensitive_search_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED_BY_POLICY"):
            web_gateway.search_web("find private key tokens")

    def test_policy_engine_web_allowlist_and_blocks(self):
        db=sqlite3.connect(":memory:")
        self.assertTrue(authorize(db,"web_public_search")["allowed"])
        for action in ("web_login","password_entry","captcha_bypass","aggressive_scraping","dangerous_download","execute_web_content","create_external_account"):
            with self.subTest(action=action):
                result=authorize(db,action);self.assertFalse(result["allowed"]);self.assertEqual(result["reason"],"BLOCKED_BY_POLICY")


if __name__ == "__main__":
    unittest.main()
