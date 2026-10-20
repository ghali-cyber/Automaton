"""Persistent local monitoring, alerts and recovery evidence."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS monitoring_samples(id TEXT PRIMARY KEY,created TEXT,service TEXT,status TEXT,latency_ms REAL,details TEXT);
    CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,created TEXT,resolved TEXT,service TEXT,severity TEXT,status TEXT,summary TEXT,evidence TEXT);
    """)


def record_sample(db, service, healthy, latency_ms, details=None):
    init_schema(db)
    status = "healthy" if healthy else "down"
    identifier = uuid.uuid4().hex
    db.execute("INSERT INTO monitoring_samples VALUES(?,?,?,?,?,?)", (identifier, _now(), service, status, max(0, float(latency_ms)), json.dumps(details or {}, ensure_ascii=False)))
    incident = None
    if not healthy:
        incident = uuid.uuid4().hex
        db.execute("INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?)", (incident, _now(), None, service, "critical", "open", f"{service} indisponible", json.dumps(details or {}, ensure_ascii=False)))
    else:
        db.execute("UPDATE incidents SET status='resolved',resolved=? WHERE service=? AND status='open'", (_now(), service))
    db.commit()
    return {"sample_id": identifier, "incident_id": incident, "status": status}


def status(db, live_health=None):
    init_schema(db)
    services = {}
    for row in db.execute("SELECT service,status,latency_ms,created FROM monitoring_samples ORDER BY created"):
        services[row[0]] = {"status": row[1], "latency_ms": row[2], "checked_at": row[3]}
    incidents = [{"id": row[0], "created": row[1], "resolved": row[2], "service": row[3], "severity": row[4], "status": row[5], "summary": row[6]} for row in db.execute("SELECT * FROM incidents ORDER BY created DESC LIMIT 50")]
    return {"services": services, "incidents": incidents, "open_incidents": sum(item["status"] == "open" for item in incidents), "live": live_health or {}, "updated_at": _now()}
