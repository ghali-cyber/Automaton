"""SQLite-backed autonomous task queue with leases, priority and bounded retries."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone


def now():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or now()).isoformat()


def init_schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS autonomous_tasks(
      id TEXT PRIMARY KEY,project_id TEXT,kind TEXT,payload TEXT,priority INTEGER,status TEXT,
      attempts INTEGER,max_attempts INTEGER,available_at TEXT,lease_until TEXT,last_error TEXT,created TEXT,updated TEXT,
      objective TEXT,max_seconds INTEGER,budget_units INTEGER,success_condition TEXT,failure_condition TEXT,result TEXT,mode TEXT)""")
    existing = {row[1] for row in db.execute("PRAGMA table_info(autonomous_tasks)")}
    migrations = {
        "objective":"TEXT DEFAULT 'Exécuter une tâche locale bornée'", "max_seconds":"INTEGER DEFAULT 900",
        "budget_units":"INTEGER DEFAULT 100", "success_condition":"TEXT DEFAULT 'handler_success'",
        "failure_condition":"TEXT DEFAULT 'max_attempts'", "result":"TEXT DEFAULT '{}'",
        "mode":"TEXT DEFAULT 'exploitation'",
    }
    for column, declaration in migrations.items():
        if column not in existing:
            db.execute("ALTER TABLE autonomous_tasks ADD COLUMN "+column+" "+declaration)


def recover_all_running(db):
    """A single-worker service restart makes every previous lease abandoned."""
    init_schema(db)
    stamp = iso()
    count = db.execute("UPDATE autonomous_tasks SET status='queued',lease_until=NULL,available_at=?,updated=? WHERE status='running'", (stamp, stamp)).rowcount
    db.commit()
    return count


def enqueue(db, project_id, kind, payload=None, priority=50, max_attempts=3, objective="Exécuter une tâche locale bornée", max_seconds=900, budget_units=100, success_condition="handler_success", failure_condition="max_attempts", mode="exploitation"):
    init_schema(db)
    identifier = uuid.uuid4().hex
    stamp = iso()
    if mode not in ("exploration","exploitation"): raise ValueError("INVALID_MODE")
    db.execute("INSERT INTO autonomous_tasks VALUES(?,?,?,?,?,'queued',0,?,?,NULL,'',?,?,?,?,?,?,?,?,?)", (identifier, project_id, kind, json.dumps(payload or {}, ensure_ascii=False), max(0, min(100, int(priority))), max(1, int(max_attempts)), stamp, stamp, stamp, str(objective)[:300], max(1,min(3600,int(max_seconds))), max(1,int(budget_units)), str(success_condition)[:200], str(failure_condition)[:200], "{}", mode))
    db.commit()
    return identifier


def recover_expired(db, at=None):
    init_schema(db)
    stamp = iso(at)
    count = db.execute("UPDATE autonomous_tasks SET status='queued',lease_until=NULL,updated=? WHERE status='running' AND lease_until<?", (stamp, stamp)).rowcount
    db.commit()
    return count


def claim(db, lease_seconds=60, at=None):
    init_schema(db)
    current = at or now(); recover_expired(db, current)
    stamp = iso(current)
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT * FROM autonomous_tasks WHERE status='queued' AND available_at<=? ORDER BY priority DESC,created,id LIMIT 1", (stamp,)).fetchone()
    if not row:
        db.commit(); return None
    identifier = row[0]
    lease_until = iso(current + timedelta(seconds=max(5, lease_seconds)))
    db.execute("UPDATE autonomous_tasks SET status='running',attempts=attempts+1,lease_until=?,updated=? WHERE id=?", (lease_until, stamp, identifier))
    db.commit()
    result = db.execute("SELECT * FROM autonomous_tasks WHERE id=?", (identifier,)).fetchone()
    keys = [item[1] for item in db.execute("PRAGMA table_info(autonomous_tasks)")]
    return dict(zip(keys, result))


def finish(db, identifier, success, error="", result=None, at=None):
    stamp = iso(at)
    row = db.execute("SELECT attempts,max_attempts FROM autonomous_tasks WHERE id=? AND status='running'", (identifier,)).fetchone()
    if not row:
        raise ValueError("TASK_NOT_RUNNING")
    attempts, maximum = row
    if success:
        db.execute("UPDATE autonomous_tasks SET status='done',lease_until=NULL,last_error='',result=?,updated=? WHERE id=?", (json.dumps(result or {},ensure_ascii=False),stamp, identifier))
        status = "done"
    elif attempts >= maximum:
        db.execute("UPDATE autonomous_tasks SET status='failed',lease_until=NULL,last_error=?,updated=? WHERE id=?", (str(error)[:300], stamp, identifier))
        status = "failed"
    else:
        delay = min(3600, 2 ** attempts)
        available = iso((at or now()) + timedelta(seconds=delay))
        db.execute("UPDATE autonomous_tasks SET status='queued',lease_until=NULL,available_at=?,last_error=?,updated=? WHERE id=?", (available, str(error)[:300], stamp, identifier))
        status = "retry"
    db.commit()
    return {"status": status, "attempts": attempts}


def queue_status(db):
    init_schema(db)
    return {row[0]:row[1] for row in db.execute("SELECT status,COUNT(*) FROM autonomous_tasks GROUP BY status")}
