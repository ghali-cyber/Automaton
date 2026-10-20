"""Local opportunity selection: quantitative evidence plus explicit qualitative gates."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS opportunity_runs(id TEXT PRIMARY KEY,created TEXT,status TEXT,selected_id TEXT,rationale TEXT);
    CREATE TABLE IF NOT EXISTS opportunities(id TEXT PRIMARY KEY,run_id TEXT,created TEXT,name TEXT,problem TEXT,target_user TEXT,channel TEXT,evidence TEXT,score REAL,status TEXT,project_id TEXT,FOREIGN KEY(run_id) REFERENCES opportunity_runs(id));
    """)


def generate_opportunities(context=None):
    """Generate reversible local opportunities from persisted Atlas signals."""
    context = context or {}
    lessons = " ".join(context.get("lessons", []))[:500]
    return [
        {"name":"SignalDesk","problem":"Les petites équipes perdent les signaux importants dispersés dans leurs notes.","target_user":"Petites équipes de service","channel":"réseau local et entretiens","hypothesis":"Une synthèse locale quotidienne réduit les oublis.","value_potential":"moyen","recurrence":"quotidienne","difficulty":"faible","build_days":2,"competition":"moyenne","differentiation":"local-first et traçable","learning_potential":"élevé","risk":"faible","reversible":True,"local_test_possible":True,"confidence":"medium","evidence":{"reachable_users":35,"pain_interviews":6,"weekly_frequency":5,"estimated_cost_eur":0,"memory_signal":lessons}},
        {"name":"StockCalm","problem":"Les micro-commerces oublient leurs seuils de stock et découvrent les ruptures trop tard.","target_user":"Micro-commerçants locaux","channel":"association locale","hypothesis":"Une alerte locale simple réduit les ruptures évitables.","value_potential":"élevé","recurrence":"hebdomadaire","difficulty":"moyenne","build_days":4,"competition":"forte","differentiation":"aucun cloud requis","learning_potential":"moyen","risk":"faible","reversible":True,"local_test_possible":True,"confidence":"medium","evidence":{"reachable_users":30,"pain_interviews":7,"weekly_frequency":4,"estimated_cost_eur":0}},
        {"name":"PublicViral","problem":"Créer une audience publique généraliste sans problème utilisateur suffisamment précis.","target_user":"Grand public","channel":"publication publique","hypothesis":"La viralité seule créera une demande.","value_potential":"incertain","recurrence":"inconnue","difficulty":"élevée","build_days":30,"competition":"très forte","differentiation":"faible","learning_potential":"faible","risk":"élevé","reversible":False,"local_test_possible":False,"confidence":"low","evidence":{"reachable_users":1000,"pain_interviews":1,"weekly_frequency":1,"estimated_cost_eur":0}},
    ]


def evaluate(candidate):
    evidence = candidate.get("evidence", {})
    reach = min(1.0, max(0.0, float(evidence.get("reachable_users", 0)) / 100))
    pain = min(1.0, max(0.0, float(evidence.get("pain_interviews", 0)) / 10))
    frequency = min(1.0, max(0.0, float(evidence.get("weekly_frequency", 0)) / 5))
    cost = min(1.0, max(0.0, 1 - float(evidence.get("estimated_cost_eur", 0)) / 50))
    score = round(100 * (0.30 * reach + 0.30 * pain + 0.25 * frequency + 0.15 * cost), 2)
    gates = {
        "specific_problem": len(str(candidate.get("problem", "")).strip()) >= 20,
        "defined_user": len(str(candidate.get("target_user", "")).strip()) >= 8,
        "reachable_channel": bool(candidate.get("channel")) and evidence.get("reachable_users", 0) >= 10,
        "local_test_possible": candidate.get("local_test_possible") is True,
        "no_real_money": evidence.get("estimated_cost_eur", 0) == 0,
        "reversible": candidate.get("reversible") is True,
        "bounded_build": 0 < int(candidate.get("build_days", 999)) <= 14,
        "learning_value": candidate.get("learning_potential") in ("moyen", "élevé"),
    }
    return score, gates


def select_opportunity(db, candidates, create_project):
    """Persist all candidates and select among those passing every qualitative gate."""
    init_schema(db)
    run_id = uuid.uuid4().hex
    db.execute("INSERT INTO opportunity_runs VALUES(?,?,?,?,?)", (run_id, _now(), "evaluating", None, ""))
    eligible = []
    for candidate in candidates:
        score, gates = evaluate(candidate)
        identifier = uuid.uuid4().hex
        evidence = dict(candidate.get("evidence", {}), qualitative_gates=gates, hypothesis=candidate.get("hypothesis"), confidence=candidate.get("confidence","low"), qualitative_analysis={key:candidate.get(key) for key in ("value_potential","recurrence","difficulty","build_days","competition","differentiation","learning_potential","risk","reversible")})
        status = "eligible" if all(gates.values()) else "rejected"
        db.execute("INSERT INTO opportunities VALUES(?,?,?,?,?,?,?,?,?,?,?)", (identifier, run_id, _now(), candidate["name"], candidate["problem"], candidate["target_user"], candidate.get("channel", ""), json.dumps(evidence, ensure_ascii=False), score, status, None))
        if status == "eligible":
            eligible.append((score, identifier, candidate, gates))
    if not eligible:
        rationale = "Aucune opportunité ne passe tous les critères qualitatifs obligatoires."
        db.execute("UPDATE opportunity_runs SET status='no_selection',rationale=? WHERE id=?", (rationale, run_id))
        db.commit()
        return {"run_id": run_id, "selected": None, "rationale": rationale}
    score, identifier, candidate, gates = max(eligible, key=lambda item: (item[0], item[2]["name"]))
    # Release the write transaction before the project factory opens Atlas' main DB.
    db.commit()
    project_id = create_project(candidate)
    db.execute("UPDATE opportunities SET status='rejected' WHERE run_id=? AND id<>?", (run_id, identifier))
    rejected = [item[0] for item in db.execute("SELECT name FROM opportunities WHERE run_id=? AND status='rejected' ORDER BY score DESC",(run_id,))]
    rationale = f"{candidate['name']} retenue: critères qualitatifs validés; score quantitatif {score}/100; confiance {candidate.get('confidence','low')}; test local à coût réel nul; alternatives rejetées: {', '.join(rejected) or 'aucune'}."
    db.execute("UPDATE opportunities SET status='selected',project_id=? WHERE id=?", (project_id, identifier))
    db.execute("UPDATE opportunity_runs SET status='selected',selected_id=?,rationale=? WHERE id=?", (identifier, rationale, run_id))
    db.commit()
    return {"run_id": run_id, "selected": identifier, "project_id": project_id, "score": score, "gates": gates, "rationale": rationale}
