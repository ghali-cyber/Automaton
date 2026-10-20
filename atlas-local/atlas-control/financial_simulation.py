"""Strictly simulated budgets and unit economics. No real payment capability."""
from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS simulation_budgets(project_id TEXT PRIMARY KEY,budget_cents INTEGER NOT NULL CHECK(budget_cents>=0),currency TEXT NOT NULL DEFAULT 'EUR',created TEXT,updated TEXT);
    CREATE TABLE IF NOT EXISTS simulation_entries(id TEXT PRIMARY KEY,project_id TEXT,kind TEXT CHECK(kind IN ('cost','revenue')),amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),category TEXT,description TEXT,created TEXT,simulation INTEGER NOT NULL CHECK(simulation=1));
    CREATE TABLE IF NOT EXISTS simulation_policy(id INTEGER PRIMARY KEY CHECK(id=1),global_budget_cents INTEGER NOT NULL,monthly_budget_cents INTEGER NOT NULL,max_expense_cents INTEGER NOT NULL,min_reserve_cents INTEGER NOT NULL,allowed_categories TEXT NOT NULL,blocked_categories TEXT NOT NULL,updated TEXT NOT NULL,simulation INTEGER NOT NULL CHECK(simulation=1));
    CREATE TABLE IF NOT EXISTS simulation_rejections(id TEXT PRIMARY KEY,project_id TEXT,amount_cents INTEGER,category TEXT,reason TEXT NOT NULL,created TEXT NOT NULL,simulation INTEGER NOT NULL CHECK(simulation=1));
    """)
    db.execute("INSERT OR IGNORE INTO simulation_policy VALUES(1,1000000,500000,100000,100000,'[]','[]',?,1)", (_now(),))


def configure(db, *, global_budget_cents, monthly_budget_cents, max_expense_cents,
              min_reserve_cents, allowed_categories=(), blocked_categories=()):
    """Persist conservative simulated-spending rules. Values are integer cents."""
    init_schema(db)
    values = [int(global_budget_cents), int(monthly_budget_cents), int(max_expense_cents), int(min_reserve_cents)]
    if any(value < 0 for value in values) or values[3] > values[0]:
        raise ValueError("SIMULATION_POLICY_INVALID")
    allowed = sorted({str(value).strip().casefold() for value in allowed_categories if str(value).strip()})
    blocked = sorted({str(value).strip().casefold() for value in blocked_categories if str(value).strip()})
    if set(allowed) & set(blocked):
        raise ValueError("SIMULATION_POLICY_CATEGORY_CONFLICT")
    db.execute("UPDATE simulation_policy SET global_budget_cents=?,monthly_budget_cents=?,max_expense_cents=?,min_reserve_cents=?,allowed_categories=?,blocked_categories=?,updated=? WHERE id=1",
               (*values, json.dumps(allowed), json.dumps(blocked), _now()))
    db.commit()
    return policy(db)


def policy(db):
    init_schema(db)
    row = db.execute("SELECT * FROM simulation_policy WHERE id=1").fetchone()
    names = [item[1] for item in db.execute("PRAGMA table_info(simulation_policy)")]
    data = dict(zip(names, row))
    data["allowed_categories"] = json.loads(data["allowed_categories"])
    data["blocked_categories"] = json.loads(data["blocked_categories"])
    data["payment_capability"] = False
    return data


def set_budget(db, project_id, budget_cents):
    init_schema(db); amount = max(0, int(budget_cents)); stamp = _now()
    db.execute("INSERT INTO simulation_budgets VALUES(?,?,'EUR',?,?) ON CONFLICT(project_id) DO UPDATE SET budget_cents=excluded.budget_cents,updated=excluded.updated", (project_id, amount, stamp, stamp))
    db.commit()


def record(db, project_id, kind, amount_cents, category, description):
    init_schema(db)
    if kind not in ("cost", "revenue"):
        raise ValueError("SIMULATION_KIND_INVALID")
    amount = int(amount_cents)
    if amount < 0:
        raise ValueError("SIMULATION_AMOUNT_INVALID")
    normalized = str(category).strip().casefold()[:80]
    rejection = None
    if kind == "cost":
        rules = policy(db)
        project_row = db.execute("SELECT budget_cents FROM simulation_budgets WHERE project_id=?", (project_id,)).fetchone()
        project_budget = project_row[0] if project_row else 0
        project_spent = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM simulation_entries WHERE project_id=? AND kind='cost'", (project_id,)).fetchone()[0]
        total_spent = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM simulation_entries WHERE kind='cost'").fetchone()[0]
        month_spent = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM simulation_entries WHERE kind='cost' AND substr(created,1,7)=?", (_now()[:7],)).fetchone()[0]
        if normalized in rules["blocked_categories"]: rejection = "CATEGORY_BLOCKED"
        elif rules["allowed_categories"] and normalized not in rules["allowed_categories"]: rejection = "CATEGORY_NOT_ALLOWED"
        elif amount > rules["max_expense_cents"]: rejection = "MAX_EXPENSE_EXCEEDED"
        elif not project_row or project_spent + amount > project_budget: rejection = "PROJECT_BUDGET_EXCEEDED"
        elif month_spent + amount > rules["monthly_budget_cents"]: rejection = "MONTHLY_BUDGET_EXCEEDED"
        elif total_spent + amount > rules["global_budget_cents"] - rules["min_reserve_cents"]: rejection = "MINIMUM_RESERVE_VIOLATED"
    if rejection:
        db.execute("INSERT INTO simulation_rejections VALUES(?,?,?,?,?,?,1)", (uuid.uuid4().hex, project_id, amount, normalized, rejection, _now()))
        db.commit()
        raise ValueError("SIMULATION_REJECTED_" + rejection)
    identifier = uuid.uuid4().hex
    db.execute("INSERT INTO simulation_entries VALUES(?,?,?,?,?,?,?,1)", (identifier, project_id, kind, amount, normalized, str(description)[:300], _now()))
    db.commit(); return identifier


def summary(db):
    init_schema(db)
    projects = {}
    ids = {row[0] for row in db.execute("SELECT project_id FROM simulation_budgets")} | {row[0] for row in db.execute("SELECT DISTINCT project_id FROM simulation_entries")}
    for project_id in sorted(ids):
        budget_row = db.execute("SELECT budget_cents FROM simulation_budgets WHERE project_id=?", (project_id,)).fetchone()
        budget = budget_row[0] if budget_row else 0
        costs = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM simulation_entries WHERE project_id=? AND kind='cost'", (project_id,)).fetchone()[0]
        revenue = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM simulation_entries WHERE project_id=? AND kind='revenue'", (project_id,)).fetchone()[0]
        profit = revenue - costs
        projects[project_id] = {"budget_cents": budget, "costs_cents": costs, "revenue_cents": revenue, "profit_cents": profit, "remaining_cents": budget - costs, "roi_percent": None if costs == 0 else round(profit / costs * 100, 2), "simulation": True}
    totals = {key: sum(project[key] for project in projects.values()) for key in ("budget_cents", "costs_cents", "revenue_cents", "profit_cents", "remaining_cents")}
    rejections = [dict(zip(("id","project_id","amount_cents","category","reason","created","simulation"), row)) for row in db.execute("SELECT * FROM simulation_rejections ORDER BY created DESC")]
    return {"label": "SIMULATION — AUCUN ARGENT RÉEL", "projects": projects, "totals": totals, "policy": policy(db), "rejections": rejections, "simulation": True, "payment_capability": False, "updated_at": _now()}
