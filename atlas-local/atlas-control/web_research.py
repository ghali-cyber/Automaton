"""Evidence-backed Web research persisted separately from generated hypotheses."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS web_research_runs(
      id TEXT PRIMARY KEY,created TEXT,completed TEXT,status TEXT,opportunity_run_id TEXT,
      selected_name TEXT,selected_project_id TEXT,query_count INTEGER,source_count INTEGER,
      independent_domains INTEGER,contradictions TEXT,rationale TEXT);
    CREATE TABLE IF NOT EXISTS web_queries(
      id TEXT PRIMARY KEY,run_id TEXT,opportunity_name TEXT,query TEXT,provider TEXT,
      retrieved_at TEXT,result_count INTEGER,status TEXT,error TEXT);
    CREATE TABLE IF NOT EXISTS web_sources(
      id TEXT PRIMARY KEY,run_id TEXT,opportunity_name TEXT,project_id TEXT,url TEXT,
      canonical_url TEXT,domain TEXT,title TEXT,published_date TEXT,retrieved_at TEXT,
      excerpt TEXT,source_type TEXT,confidence TEXT,claim_type TEXT,content_hash TEXT,
      entity_key TEXT,duplicate_of TEXT,status TEXT,metadata TEXT);
    CREATE INDEX IF NOT EXISTS web_sources_run_idx ON web_sources(run_id,opportunity_name);
    CREATE INDEX IF NOT EXISTS web_sources_url_idx ON web_sources(canonical_url);
    """)


def canonical_url(value):
    parsed = urlsplit(str(value).strip())
    query = urlencode(sorted((key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True) if not key.casefold().startswith("utm_") and key.casefold() not in {"ref", "source", "campaign"}))
    return urlunsplit((parsed.scheme.casefold(), (parsed.hostname or "").casefold(), re.sub("/+", "/", parsed.path or "/").rstrip("/") or "/", query, ""))


def _normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _entity_key(title, domain):
    stop = {"the", "and", "for", "with", "from", "les", "des", "pour", "une", "official", "home"}
    words = [word for word in _normalized(title).split() if word not in stop][:5]
    return ("-".join(words) or domain)[:160]


def _claim_type(source):
    text = (source.get("title", "") + " " + source.get("excerpt", "")).casefold()
    if re.search(r"\b(opinion|commentary|editorial|avis)\b", text):
        return "opinion"
    if re.search(r"\b(estimate|forecast|projected|estimated|prévision|estimation)\b", text):
        return "estimate"
    return "fact_reported_by_source"


def store_source(db, run_id, opportunity_name, source, search_metadata=None):
    init_schema(db)
    canonical = canonical_url(source["url"])
    excerpt = re.sub(r"\s+", " ", str(source.get("excerpt", ""))).strip()[:6000]
    digest = hashlib.sha256(_normalized(excerpt).encode()).hexdigest()
    domain = str(source.get("domain") or urlsplit(canonical).hostname or "")[:253]
    entity = _entity_key(source.get("title", ""), domain)
    duplicate = db.execute("SELECT id FROM web_sources WHERE run_id=? AND canonical_url=? AND status='stored' LIMIT 1", (run_id, canonical)).fetchone()
    if not duplicate:
        for row in db.execute("SELECT id,excerpt,domain,entity_key FROM web_sources WHERE run_id=? AND opportunity_name=? AND status='stored'", (run_id, opportunity_name)):
            similar = SequenceMatcher(None, _normalized(excerpt)[:3000], _normalized(row[1])[:3000]).ratio() if excerpt and row[1] else 0
            if similar >= 0.88 or (domain == row[2] and entity == row[3]):
                duplicate = (row[0],)
                break
    identifier = uuid.uuid4().hex
    status = "duplicate" if duplicate else "stored"
    confidence = "medium" if source.get("source_type") in ("public_authority", "academic", "documentation") else "low"
    db.execute("INSERT INTO web_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        identifier, run_id, opportunity_name, None, source["url"], canonical, domain,
        str(source.get("title", domain))[:300], source.get("date"), source.get("retrieved_at", _now()),
        excerpt, str(source.get("source_type", "public_web"))[:80], confidence,
        _claim_type(source), digest, entity, duplicate[0] if duplicate else None, status,
        json.dumps(search_metadata or {}, ensure_ascii=False),
    ))
    db.commit()
    return {"id": identifier, "status": status, "duplicate_of": duplicate[0] if duplicate else None}


def _queries(candidate):
    if candidate.get("research_queries"):
        return [str(item)[:200] for item in candidate["research_queries"][:2]]
    name = candidate["name"]
    target = candidate["target_user"]
    problem = candidate["problem"]
    return [f'"{name}" OR "{problem[:70]}" {target} software market competitors pricing']


def _price_observations(text):
    matches = re.findall(r"(?:[$€£]\s?\d+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?\s?(?:USD|EUR|GBP))", text, re.I)
    return list(dict.fromkeys(matches))[:12]


def _contradictions(excerpts):
    joined = " ".join(excerpts).casefold()
    pairs = [(("growing", "growth", "increase", "hausse", "croissance"), ("decline", "decrease", "falling", "baisse", "recul")), (("easy", "simple", "facile"), ("difficult", "complex", "difficile", "complexe"))]
    found = []
    for positive, negative in pairs:
        left = next((word for word in positive if word in joined), None)
        right = next((word for word in negative if word in joined), None)
        if left and right:
            found.append({"type": "language_signal", "terms": [left, right], "requires_human_interpretation": True})
    return found


def research_candidates(db, candidates, broker, max_open_per_candidate=2):
    init_schema(db)
    run_id = uuid.uuid4().hex
    db.execute("INSERT INTO web_research_runs VALUES(?,?,NULL,'running',NULL,NULL,NULL,0,0,0,'[]','')", (run_id, _now()))
    enriched = []
    query_count = 0
    for candidate in candidates[:3]:
        candidate = json.loads(json.dumps(candidate, ensure_ascii=False))
        errors = []
        for query in _queries(candidate):
            query_count += 1
            query_id = uuid.uuid4().hex
            try:
                search = broker("web_search", query=query)
                results = search.get("results", [])
                db.execute("INSERT INTO web_queries VALUES(?,?,?,?,?,?,?,?,?)", (query_id, run_id, candidate["name"], query, search.get("provider", "unknown"), search.get("retrieved_at", _now()), len(results), "success", ""))
                opened = 0
                for result in results[:5]:
                    if opened >= max_open_per_candidate:
                        break
                    try:
                        source = broker("web_read", url=result["url"])
                        stored = store_source(db, run_id, candidate["name"], source, {"query": query, "search_title": result.get("title"), "search_date": result.get("date")})
                        if stored["status"] == "stored":
                            opened += 1
                    except Exception as error:
                        errors.append(type(error).__name__ + ": " + str(error)[:160])
            except Exception as error:
                db.execute("INSERT INTO web_queries VALUES(?,?,?,?,?,?,?,?,?)", (query_id, run_id, candidate["name"], query, "unavailable", _now(), 0, "failed", str(error)[:300]))
                errors.append(type(error).__name__ + ": " + str(error)[:160])
            db.commit()
        rows = list(db.execute("SELECT id,url,domain,title,published_date,retrieved_at,excerpt,source_type,confidence,claim_type FROM web_sources WHERE run_id=? AND opportunity_name=? AND status='stored' ORDER BY retrieved_at", (run_id, candidate["name"])))
        domains = sorted({row[2] for row in rows})
        excerpts = [row[6] for row in rows]
        sources = [{"id": row[0], "url": row[1], "domain": row[2], "title": row[3], "date": row[4], "retrieved_at": row[5], "excerpt": row[6][:800], "source_type": row[7], "confidence": row[8], "claim_type": row[9]} for row in rows]
        observed_prices = _price_observations(" ".join(excerpts))
        contradictions = _contradictions(excerpts)
        confidence = "high" if len(domains) >= 3 else "medium" if len(domains) >= 2 else "low"
        evidence = candidate.setdefault("evidence", {})
        evidence.update({"web_research_run_id": run_id, "web_evidence_count": len(sources), "independent_domains": len(domains), "sources": sources, "price_observations": observed_prices, "contradictions": contradictions, "hypotheses_unverified": [candidate.get("hypothesis", "")], "web_errors": errors[:8]})
        candidate["confidence"] = confidence
        candidate["web_analysis"] = {"need_evidence": [item["excerpt"] for item in sources[:2]], "competitors_or_products": sorted({_entity_key(item["title"], item["domain"]) for item in sources}), "prices_observed": observed_prices, "advantages": [candidate.get("differentiation", "")], "disadvantages": [candidate.get("competition", "")], "economic_potential": candidate.get("value_potential"), "confidence": confidence, "contradictions": contradictions}
        enriched.append(candidate)
    source_count = db.execute("SELECT COUNT(*) FROM web_sources WHERE run_id=? AND status='stored'", (run_id,)).fetchone()[0]
    domain_count = db.execute("SELECT COUNT(DISTINCT domain) FROM web_sources WHERE run_id=? AND status='stored'", (run_id,)).fetchone()[0]
    complete_candidates = sum(
        1 for candidate in enriched
        if candidate["evidence"]["web_evidence_count"] >= 2
        and candidate["evidence"]["independent_domains"] >= 2
    )
    all_contradictions = [item for candidate in enriched for item in candidate["web_analysis"]["contradictions"]]
    status = "researched" if len(enriched) == 3 and complete_candidates == 3 else "insufficient_evidence"
    db.execute("UPDATE web_research_runs SET completed=?,status=?,query_count=?,source_count=?,independent_domains=?,contradictions=?,rationale=? WHERE id=?", (_now(), status, query_count, source_count, domain_count, json.dumps(all_contradictions, ensure_ascii=False), f"{len(enriched)} opportunités recherchées; {complete_candidates} avec au moins 2 sources et 2 domaines; {source_count} sources uniques sur {domain_count} domaines.", run_id))
    db.commit()
    return {"run_id": run_id, "status": status, "candidates": enriched, "query_count": query_count, "source_count": source_count, "independent_domains": domain_count, "complete_candidates": complete_candidates}


def link_selection(db, research_run_id, opportunity_run_id, selected_name, project_id):
    db.execute("UPDATE web_research_runs SET opportunity_run_id=?,selected_name=?,selected_project_id=? WHERE id=?", (opportunity_run_id, selected_name, project_id, research_run_id))
    db.execute("UPDATE web_sources SET project_id=? WHERE run_id=? AND opportunity_name=?", (project_id, research_run_id, selected_name))
    db.commit()
