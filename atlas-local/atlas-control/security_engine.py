"""Deny-by-default Atlas policy decisions with a persistent audit trail."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

SAFE_LOCAL = {"read_state", "write_workspace", "run_tests", "local_preview", "ollama_inference", "n8n_allowlisted"}
BLOCKED = {
    "send_email": "draft_only",
    "public_deploy": "local_preview",
    "payment": "financial_simulation",
    "crypto_transaction": "paper_simulation",
    "paid_api": "local_or_free_model",
    "delete_irreversible": "copy_then_review",
    "external_message": "draft_only",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS policy_audit(id TEXT PRIMARY KEY,created TEXT,actor TEXT,action TEXT,allowed INTEGER,reason TEXT,safe_alternative TEXT,context TEXT)")


def authorize(db, action, actor="atlas", context=None):
    init_schema(db)
    if action in SAFE_LOCAL:
        allowed, reason, alternative = True, "LOCAL_ALLOWLIST", ""
    elif action in BLOCKED:
        allowed, reason, alternative = False, "BLOCKED_BY_POLICY", BLOCKED[action]
    else:
        allowed, reason, alternative = False, "UNKNOWN_ACTION_DENIED", "manual_review"
    record = {"id": uuid.uuid4().hex, "created": _now(), "actor": actor, "action": action, "allowed": allowed, "reason": reason, "safe_alternative": alternative, "context": context or {}}
    db.execute("INSERT INTO policy_audit VALUES(?,?,?,?,?,?,?,?)", (record["id"], record["created"], actor, action, int(allowed), reason, alternative, json.dumps(record["context"], ensure_ascii=False)))
    db.commit()
    return record
