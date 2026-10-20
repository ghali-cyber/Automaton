"""Persistent, explainable cross-project experience memory for Atlas."""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone

FAILURE_DIMENSIONS = ("bug", "ux", "pricing", "message", "segment", "channel", "distribution", "traffic", "no_demand")


def now():
    return datetime.now(timezone.utc).isoformat()


def classify_failure(text):
    value = str(text or "").casefold()
    rules = {
        "bug": ("bug", "erreur", "exception", "crash", "test échou"),
        "ux": ("ux", "parcours", "confus", "interface"),
        "pricing": ("prix", "tarif", "pricing", "trop cher"),
        "message": ("message", "promesse", "proposition de valeur"),
        "segment": ("segment", "persona", "cible"),
        "channel": ("canal", "channel", "email", "réseau"),
        "distribution": ("distribution", "acquisition", "diffusion"),
        "traffic": ("trafic", "visite", "audience"),
        "no_demand": ("aucune demande", "pas de demande", "no demand"),
    }
    for dimension, words in rules.items():
        if any(word in value for word in words):
            return dimension
    return "bug"


def _tokens(value):
    stop = {"application", "type", "lessons", "failure", "dimension", "améliorer", "clarifier", "mauvais", "faible"}
    return set(re.findall(r"[a-z0-9à-ÿ]{3,}", json.dumps(value, ensure_ascii=False).casefold())) - stop


def relevant_cross_project(connection, project_id, specification, limit=5):
    """Return only useful memories from other projects with an auditable score."""
    wanted = _tokens(specification)
    rows = connection.execute("SELECT id,project_id,created,payload FROM experiences WHERE project_id IS NOT NULL AND project_id<>? ORDER BY created DESC", (project_id,)).fetchall()
    ranked = []
    for row in rows:
        payload = json.loads(row["payload"] if isinstance(row, sqlite3.Row) else row[3])
        overlap = wanted & _tokens({"lessons": payload.get("lessons", []), "failure_dimension": payload.get("failure_dimension"), "application_type": payload.get("application_type")})
        same_domain = payload.get("application_type") == specification.get("application_type")
        if same_domain or len(overlap) >= 2:
            ranked.append({"id": row["id"], "project_id": row["project_id"], "created": row["created"], "score": len(overlap), "matched_terms": sorted(overlap), "lessons": payload.get("lessons", [])})
    return sorted(ranked, key=lambda item: (-item["score"], item["created"]), reverse=False)[:limit]


def record_experience(connection, project_id, payload):
    clean = dict(payload)
    clean["failure_dimension"] = clean.get("failure_dimension") or classify_failure(" ".join(clean.get("failed", [])))
    clean["confidence"] = clean.get("confidence", "low")
    clean["estimated_cost_eur"] = max(0, float(clean.get("estimated_cost_eur", 0)))
    clean["estimated_minutes"] = max(0, float(clean.get("estimated_minutes", 0)))
    identifier = uuid.uuid4().hex
    connection.execute("INSERT INTO experiences(id,project_id,created,payload) VALUES(?,?,?,?)", (identifier, project_id, now(), json.dumps(clean, ensure_ascii=False)))
    return identifier
