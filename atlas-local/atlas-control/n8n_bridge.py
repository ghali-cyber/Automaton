"""Credential-free Atlas↔n8n local bridge with a strict workflow allowlist."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

WORKFLOWS = {
    "AtlasDataTransform001": "data-transform",
    "AtlasLocalReport001": "local-report",
    "AtlasTaskProcess001": "atlas-task-processing",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS workflow_runs(id TEXT PRIMARY KEY,workflow_id TEXT,created TEXT,status TEXT,input TEXT,result TEXT,error TEXT)")


def invoke(db, workflow_id, payload):
    init_schema(db)
    if workflow_id not in WORKFLOWS:
        raise ValueError("WORKFLOW_NOT_ALLOWLISTED")
    if not isinstance(payload, dict) or len(json.dumps(payload)) > 8192:
        raise ValueError("INVALID_PAYLOAD")
    identifier = uuid.uuid4().hex
    db.execute("INSERT INTO workflow_runs VALUES(?,?,?,?,?,?,?)", (identifier, workflow_id, _now(), "running", json.dumps(payload, ensure_ascii=False), "{}", ""))
    try:
        if workflow_id == "AtlasDataTransform001":
            rows = payload.get("rows")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError("INVALID_ROWS")
            result = {"count": len(rows), "rows": [{str(k).strip().casefold(): v for k, v in row.items()} for row in rows], "external_actions": False}
        elif workflow_id == "AtlasLocalReport001":
            title = str(payload.get("title", "Rapport Atlas"))[:100]
            metrics = payload.get("metrics", {})
            if not isinstance(metrics, dict):
                raise ValueError("INVALID_METRICS")
            result = {"report": title + "\n" + "\n".join(f"- {key}: {value}" for key, value in sorted(metrics.items())), "format": "text", "external_actions": False}
        else:
            task = payload.get("task")
            if not isinstance(task, dict) or not task.get("id"):
                raise ValueError("INVALID_TASK")
            result = {"task_id": str(task["id"]), "status": "processed", "next_action": str(task.get("next_action", "continue"))[:100], "external_actions": False}
        db.execute("UPDATE workflow_runs SET status='success',result=? WHERE id=?", (json.dumps(result, ensure_ascii=False), identifier))
        db.commit()
        return {"run_id": identifier, **result}
    except Exception as error:
        db.execute("UPDATE workflow_runs SET status='failed',error=? WHERE id=?", (str(error)[:160], identifier))
        db.commit()
        raise
