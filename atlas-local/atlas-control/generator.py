"""Deterministic, specification-driven local prototype generator for Atlas."""
from __future__ import annotations

import html
import json
import re


REQUIRED_SPEC_FIELDS = (
    "name", "description", "application_type", "target_user", "pages",
    "navigation", "features", "entities", "interactions", "theme",
    "storage", "api", "test_criteria",
)


def _clean_text(value, default, limit=500):
    if not isinstance(value, str):
        return default
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] or default


def _clean_list(value, default):
    if not isinstance(value, list):
        return list(default)
    cleaned = [_clean_text(item, "", 120) for item in value]
    return [item for item in cleaned if item][:20] or list(default)


def application_type(idea):
    text = idea.casefold()
    if any(word in text for word in ("musique", "musical", "playlist", "album", "artiste", "lecteur")):
        return "music-library"
    if any(word in text for word in ("demande", "ticket", "support", "client", "priorité", "queuepilot")):
        return "request-management"
    if any(word in text for word in ("boutique", "commerce", "panier", "produit", "commande")):
        return "mini-commerce"
    if any(word in text for word in ("crm", "prospect", "pipeline", "vente", "commercial")):
        return "crm"
    if any(word in text for word in ("productivité", "assistant ia", "notes ia", "résumé", "prioriser")):
        return "ai-productivity"
    return "generic-workspace"


def default_name(kind):
    return {
        "music-library": "Musea",
        "request-management": "FlowDesk",
        "mini-commerce": "Cartly",
        "crm": "Relatio",
        "ai-productivity": "FocusAI",
        "generic-workspace": "Nexa",
    }[kind]


def build_specification(idea, supplied=None):
    """Return a complete, bounded specification. Supplied values override safe defaults."""
    supplied = supplied if isinstance(supplied, dict) else {}
    kind = _clean_text(supplied.get("application_type"), application_type(idea), 80)
    if kind not in ("music-library", "request-management", "mini-commerce", "crm", "ai-productivity", "generic-workspace"):
        kind = application_type(idea)
    if kind == "music-library":
        defaults = {
            "name": "Musea",
            "description": "Bibliothèque musicale locale premium pour explorer un catalogue entièrement fictif.",
            "target_user": "Amateurs de musique souhaitant organiser une bibliothèque de démonstration locale.",
            "pages": ["Accueil", "Recherche", "Bibliothèque", "Artiste", "Album"],
            "navigation": ["Accueil", "Recherche", "Bibliothèque"],
            "features": ["Recommandations", "Nouveautés", "Playlists", "Recherche", "Favoris", "Lecteur visuel"],
            "entities": ["Artiste", "Album", "Morceau", "Playlist", "Favori"],
            "interactions": ["Rechercher", "Ouvrir un artiste", "Ouvrir un album", "Ajouter aux favoris", "Contrôler le lecteur"],
            "theme": {"background": "#ffffff", "primary": "#ff2d8d", "accent": "#ff68b4", "style": "premium, blanc et rose avec dégradés subtils"},
            "storage": "localStorage isolé par projet pour les favoris et la progression de démonstration",
            "api": "Aucune API externe ou payante",
            "test_criteria": ["Navigation fonctionnelle", "Recherche locale", "Favoris persistants", "Catalogue fictif", "Domaine musical exclusivement"],
        }
    elif kind == "request-management":
        defaults = {
            "name": "FlowDesk",
            "description": "Espace local pour organiser et suivre les demandes d'une équipe.",
            "target_user": "Petites équipes de service et de coordination.",
            "pages": ["Vue d'ensemble", "Demandes", "Équipe"],
            "navigation": ["Vue d'ensemble", "Demandes", "Équipe"],
            "features": ["Création", "Recherche", "Filtrage", "Suivi", "Synthèse"],
            "entities": ["Demande", "Contact", "Priorité", "Statut"],
            "interactions": ["Créer", "Rechercher", "Filtrer", "Mettre à jour"],
            "theme": {"background": "#f6f8fb", "primary": "#3157d5", "accent": "#20a39e", "style": "professionnel et structuré"},
            "storage": "SQLite local isolé par projet",
            "api": "API locale uniquement",
            "test_criteria": ["Validation des champs", "Recherche", "Persistance", "Isolation du projet"],
        }
    elif kind == "mini-commerce":
        defaults = {
            "name": "Cartly", "description": "Mini-commerce local avec catalogue, panier et commandes fictives.",
            "target_user": "Petits commerçants validant un parcours de vente sans paiement réel.",
            "pages": ["Catalogue", "Panier", "Commandes"], "navigation": ["Catalogue", "Panier", "Commandes"],
            "features": ["Catalogue", "Recherche produit", "Panier simulé", "Suivi de commande"],
            "entities": ["Produit", "Panier", "Commande"],
            "interactions": ["Rechercher", "Ajouter au panier", "Modifier une quantité", "Créer une commande simulée"],
            "theme": {"background": "#fffaf2", "primary": "#c44b22", "accent": "#ef9f32", "style": "commerce chaleureux et lisible"},
            "storage": "localStorage isolé par projet et version", "api": "Aucun paiement ni API externe",
            "test_criteria": ["Catalogue distinct", "Panier persistant", "Aucun paiement réel", "Isolation du projet"],
        }
    elif kind == "crm":
        defaults = {
            "name": "Relatio", "description": "CRM local pour suivre prospects, échanges et opportunités fictives.",
            "target_user": "Petites équipes commerciales travaillant hors ligne.",
            "pages": ["Pipeline", "Contacts", "Activités"], "navigation": ["Pipeline", "Contacts", "Activités"],
            "features": ["Pipeline", "Fiches contact", "Relances", "Historique"],
            "entities": ["Prospect", "Opportunité", "Activité"],
            "interactions": ["Créer un prospect", "Déplacer une opportunité", "Planifier une relance"],
            "theme": {"background": "#f3f7ff", "primary": "#2457c5", "accent": "#33a6a0", "style": "tableau commercial clair"},
            "storage": "SQLite local isolé par projet", "api": "API locale seulement",
            "test_criteria": ["Pipeline fonctionnel", "Contacts distincts", "Historique persistant", "Isolation du projet"],
        }
    elif kind == "ai-productivity":
        defaults = {
            "name": "FocusAI", "description": "Assistant local de productivité pour résumer et prioriser des notes fictives.",
            "target_user": "Professionnels organisant leurs tâches avec un modèle local.",
            "pages": ["Boîte de réception", "Priorités", "Synthèses"], "navigation": ["Boîte de réception", "Priorités", "Synthèses"],
            "features": ["Capture de notes", "Résumé local", "Priorisation", "Historique"],
            "entities": ["Note", "Tâche", "Synthèse"],
            "interactions": ["Ajouter une note", "Générer une synthèse locale", "Changer une priorité"],
            "theme": {"background": "#f7f5ff", "primary": "#6542c7", "accent": "#22a7a0", "style": "assistant calme et concentré"},
            "storage": "Stockage local isolé par projet", "api": "Ollama local uniquement",
            "test_criteria": ["Résumé marqué fictif", "Priorités modifiables", "Aucun appel externe", "Isolation du projet"],
        }
    else:
        defaults = {
            "name": "Nexa",
            "description": _clean_text(idea, "Application locale générée depuis une spécification."),
            "target_user": "Utilisateur du produit décrit",
            "pages": ["Accueil", "Espace", "Détails"],
            "navigation": ["Accueil", "Espace", "Détails"],
            "features": ["Consultation", "Recherche", "Organisation"],
            "entities": ["Élément", "Collection"],
            "interactions": ["Naviguer", "Rechercher", "Sélectionner"],
            "theme": {"background": "#f8fafc", "primary": "#6d5dfc", "accent": "#20c4b4", "style": "moderne et accessible"},
            "storage": "Stockage local isolé par projet",
            "api": "Aucune API externe par défaut",
            "test_criteria": ["Navigation", "Affichage des données", "Isolation du projet"],
        }
    theme = supplied.get("theme") if isinstance(supplied.get("theme"), dict) else defaults["theme"]
    spec = {
        "name": _clean_text(supplied.get("name"), defaults["name"], 50),
        "description": _clean_text(supplied.get("description"), defaults["description"], 500),
        "application_type": kind,
        "target_user": _clean_text(supplied.get("target_user"), defaults["target_user"], 300),
        "pages": _clean_list(supplied.get("pages"), defaults["pages"]),
        "navigation": _clean_list(supplied.get("navigation"), defaults["navigation"]),
        "features": _clean_list(supplied.get("features"), defaults["features"]),
        "entities": _clean_list(supplied.get("entities"), defaults["entities"]),
        "interactions": _clean_list(supplied.get("interactions"), defaults["interactions"]),
        "theme": {
            "background": _clean_text(theme.get("background"), defaults["theme"]["background"], 20),
            "primary": _clean_text(theme.get("primary"), defaults["theme"]["primary"], 20),
            "accent": _clean_text(theme.get("accent"), defaults["theme"]["accent"], 20),
            "style": _clean_text(theme.get("style"), defaults["theme"]["style"], 200),
        },
        "storage": _clean_text(supplied.get("storage"), defaults["storage"], 300),
        "api": _clean_text(supplied.get("api"), defaults["api"], 300),
        "test_criteria": _clean_list(supplied.get("test_criteria"), defaults["test_criteria"]),
    }
    return spec


def concept_key(spec):
    return re.sub(r"[^a-z0-9]+", "-", spec["application_type"].casefold()).strip("-")


def bump_version(current, change_type):
    try:
        major, minor, patch = [int(part) for part in current.split(".")]
    except Exception:
        major, minor, patch = 1, 0, 0
    if change_type == "major":
        major, minor, patch = major + 1, 0, 0
    elif change_type == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def classify_change(idea):
    text = idea.casefold()
    if any(word in text for word in ("refonte", "architecture", "redesign complet", "majeure")):
        return "major"
    if any(word in text for word in ("ajoute", "nouvelle fonctionnalité", "fonctionnalité", "améliore", "amélioration")):
        return "minor"
    return "patch"


def _music_files(spec, project_id, version):
    catalog = {
        "artists": [
            {"id": "a1", "name": "Naya Sol", "genre": "Électro solaire", "accent": "#ff2d8d"},
            {"id": "a2", "name": "Velours Nord", "genre": "Pop nocturne", "accent": "#8b5cf6"},
            {"id": "a3", "name": "Iris Mallow", "genre": "Soul futuriste", "accent": "#ff7ab8"},
            {"id": "a4", "name": "Kumo Lane", "genre": "Dream wave", "accent": "#36c5f0"},
        ],
        "albums": [
            {"id": "al1", "title": "Rose Magnétique", "artist": "Naya Sol", "year": "2026", "cover": "linear-gradient(135deg,#ff2d8d,#ff9bca)"},
            {"id": "al2", "title": "Minuit Velours", "artist": "Velours Nord", "year": "2026", "cover": "linear-gradient(135deg,#3b176e,#d946ef)"},
            {"id": "al3", "title": "Lueurs Parallèles", "artist": "Iris Mallow", "year": "2025", "cover": "linear-gradient(135deg,#fb7185,#fbcfe8)"},
            {"id": "al4", "title": "Nuages Chromés", "artist": "Kumo Lane", "year": "2026", "cover": "linear-gradient(135deg,#0891b2,#a5f3fc)"},
        ],
        "tracks": [
            {"id": "t1", "title": "Lumière sur toi", "artist": "Naya Sol", "album": "Rose Magnétique", "duration": "3:18"},
            {"id": "t2", "title": "Éclat secret", "artist": "Naya Sol", "album": "Rose Magnétique", "duration": "2:54"},
            {"id": "t3", "title": "Après minuit", "artist": "Velours Nord", "album": "Minuit Velours", "duration": "3:42"},
            {"id": "t4", "title": "Sans gravité", "artist": "Iris Mallow", "album": "Lueurs Parallèles", "duration": "3:07"},
            {"id": "t5", "title": "Ciel liquide", "artist": "Kumo Lane", "album": "Nuages Chromés", "duration": "4:02"},
            {"id": "t6", "title": "Pétale électrique", "artist": "Iris Mallow", "album": "Lueurs Parallèles", "duration": "2:49"},
        ],
        "playlists": [
            {"id": "p1", "title": "Énergie rose", "subtitle": "Pop vive et lumineuse", "track_ids": ["t1", "t2", "t6"]},
            {"id": "p2", "title": "Nuit satinée", "subtitle": "Textures douces après minuit", "track_ids": ["t3", "t4", "t5"]},
            {"id": "p3", "title": "Nouveaux horizons", "subtitle": "Sélection fictive 2026", "track_ids": ["t5", "t1", "t4"]},
        ],
    }
    data_json = json.dumps(catalog, ensure_ascii=False)
    spec_json = json.dumps(spec, ensure_ascii=False)
    storage_key = f"atlas:{project_id}:v{version}:music"
    html_doc = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(spec['name'])} — musique locale</title><link rel="stylesheet" href="style.css"><script src="prototype.js" defer></script></head><body><div class="ambient one"></div><div class="ambient two"></div><div class="app"><aside><div class="brand"><span>♪</span>{html.escape(spec['name'])}</div><nav><button class="active" data-view="home">⌂ Accueil</button><button data-view="search">⌕ Recherche</button><button data-view="library">♡ Bibliothèque</button></nav><div class="demo">DÉMO LOCALE — DONNÉES FICTIVES</div><p class="fine">Catalogue original de démonstration.<br>Aucune musique réelle.</p></aside><main><header><div><small>EXPÉRIENCE MUSICALE LOCALE</small><h1 id="page-title">Pour vous</h1></div><div class="profile">HP</div></header><section id="content"></section></main></div><footer class="player"><div class="now"><div class="mini-cover"></div><div><strong id="now-title">Lumière sur toi</strong><span id="now-artist">Naya Sol</span></div><button id="favorite" aria-label="Ajouter aux favoris">♡</button></div><div class="transport"><div><button id="previous">◀</button><button id="play" class="play">▶</button><button id="next">▶▶</button></div><input id="progress" type="range" min="0" max="100" value="32" aria-label="Progression"></div><div class="volume">⌁ <input id="volume" type="range" min="0" max="100" value="72" aria-label="Volume"></div></footer></body></html>'''
    js = f'''const CATALOG={data_json};const SPEC={spec_json};const KEY={json.dumps(storage_key)};const $=s=>document.querySelector(s);const esc=s=>String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));let saved=JSON.parse(localStorage.getItem(KEY)||'{{"favorites":[],"track":"t1","playing":false}}');let view='home';let detail=null;const track=id=>CATALOG.tracks.find(x=>x.id===id)||CATALOG.tracks[0];function persist(){{localStorage.setItem(KEY,JSON.stringify(saved))}}function cover(a,extra=''){{return `<article class="cover-card ${{extra}}" data-album="${{a.id}}"><div class="cover" style="background:${{a.cover}}"><span>♪</span></div><strong>${{esc(a.title)}}</strong><small>${{esc(a.artist)}}</small></article>`}}function artist(a){{return `<article class="artist-card" data-artist="${{a.id}}"><div style="--accent:${{a.accent}}">${{esc(a.name.slice(0,1))}}</div><strong>${{esc(a.name)}}</strong><small>${{esc(a.genre)}}</small></article>`}}function trackRow(t){{const fav=saved.favorites.includes(t.id);return `<button class="track" data-track="${{t.id}}"><span class="track-play">▶</span><span><strong>${{esc(t.title)}}</strong><small>${{esc(t.artist)}} · ${{esc(t.album)}}</small></span><i>${{fav?'♥':'♡'}}</i><time>${{t.duration}}</time></button>`}}function section(title,body,action=''){{return `<div class="section-head"><h2>${{title}}</h2>${{action}}</div><div class="grid">${{body}}</div>`}}function home(){{return `<div class="hero"><div><span>NOUVEAU MIX</span><h2>Le rose prend<br>le rythme.</h2><p>Une sélection locale, élégante et entièrement fictive.</p><button data-track="t1">Écouter la sélection</button></div><div class="hero-disc"><i>♪</i></div></div>${{section('Recommandations',CATALOG.playlists.map(p=>`<article class="playlist"><div>♫</div><strong>${{esc(p.title)}}</strong><small>${{esc(p.subtitle)}}</small></article>`).join(''))}}${{section('Nouveautés',CATALOG.albums.map(cover).join(''))}}${{section('Artistes à suivre',CATALOG.artists.map(artist).join(''))}}`}}function search(){{return `<label class="search"><span>⌕</span><input id="query" autofocus placeholder="Titre, artiste ou album"></label><div id="results">${{section('Tout le catalogue',CATALOG.tracks.map(trackRow).join(''),'')}}</div>`}}function library(){{const items=CATALOG.tracks.filter(t=>saved.favorites.includes(t.id));return `<div class="library-hero"><span>♡</span><div><small>VOTRE ESPACE</small><h2>Bibliothèque</h2><p>Vos favoris restent enregistrés localement dans cette version.</p></div></div>${{section('Morceaux favoris',items.length?items.map(trackRow).join(''):'<div class="empty">Ajoutez un cœur depuis le lecteur ou une piste.</div>')}}${{section('Playlists',CATALOG.playlists.map(p=>`<article class="playlist"><div>♫</div><strong>${{esc(p.title)}}</strong><small>${{p.track_ids.length}} titres fictifs</small></article>`).join(''))}}`}}function albumPage(id){{const a=CATALOG.albums.find(x=>x.id===id),items=CATALOG.tracks.filter(t=>t.album===a.title);return `<button class="back" data-back>← Retour</button><div class="detail"><div class="cover large" style="background:${{a.cover}}"><span>♪</span></div><div><small>ALBUM FICTIF · ${{a.year}}</small><h2>${{esc(a.title)}}</h2><p>${{esc(a.artist)}}</p><button data-track="${{items[0]?.id}}">▶ Lecture</button></div></div><div class="tracks">${{items.map(trackRow).join('')}}</div>`}}function artistPage(id){{const a=CATALOG.artists.find(x=>x.id===id),items=CATALOG.tracks.filter(t=>t.artist===a.name);return `<button class="back" data-back>← Retour</button><div class="artist-detail" style="--accent:${{a.accent}}"><div>${{esc(a.name.slice(0,1))}}</div><small>ARTISTE FICTIF</small><h2>${{esc(a.name)}}</h2><p>${{esc(a.genre)}}</p></div>${{section('Titres populaires',items.map(trackRow).join(''))}}`}}function render(){{document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===view&&!detail));$('#page-title').textContent=detail?.type==='album'?'Album':detail?.type==='artist'?'Artiste':view==='home'?'Pour vous':view==='search'?'Recherche':'Bibliothèque';$('#content').innerHTML=detail?(detail.type==='album'?albumPage(detail.id):artistPage(detail.id)):(view==='home'?home():view==='search'?search():library());if(view==='search'&&!detail)$('#query').addEventListener('input',e=>{{const q=e.target.value.toLowerCase(),items=CATALOG.tracks.filter(t=>[t.title,t.artist,t.album].some(x=>x.toLowerCase().includes(q)));$('#results').innerHTML=section(items.length?'Résultats':'Aucun résultat',items.map(trackRow).join('')||'<div class="empty">Essayez un autre terme.</div>')}});syncPlayer()}}function syncPlayer(){{const t=track(saved.track);$('#now-title').textContent=t.title;$('#now-artist').textContent=t.artist;$('#favorite').textContent=saved.favorites.includes(t.id)?'♥':'♡';$('#play').textContent=saved.playing?'Ⅱ':'▶'}}document.addEventListener('click',e=>{{const nav=e.target.closest('[data-view]');if(nav){{view=nav.dataset.view;detail=null;render();return}}const al=e.target.closest('[data-album]');if(al){{detail={{type:'album',id:al.dataset.album}};render();return}}const ar=e.target.closest('[data-artist]');if(ar){{detail={{type:'artist',id:ar.dataset.artist}};render();return}}if(e.target.closest('[data-back]')){{detail=null;render();return}}const tr=e.target.closest('[data-track]');if(tr?.dataset.track){{saved.track=tr.dataset.track;saved.playing=true;persist();syncPlayer()}}}});$('#play').onclick=()=>{{saved.playing=!saved.playing;persist();syncPlayer()}};$('#favorite').onclick=()=>{{const id=saved.track;saved.favorites=saved.favorites.includes(id)?saved.favorites.filter(x=>x!==id):[...saved.favorites,id];persist();render()}};$('#next').onclick=()=>{{const i=CATALOG.tracks.findIndex(x=>x.id===saved.track);saved.track=CATALOG.tracks[(i+1)%CATALOG.tracks.length].id;persist();syncPlayer()}};$('#previous').onclick=()=>{{const i=CATALOG.tracks.findIndex(x=>x.id===saved.track);saved.track=CATALOG.tracks[(i-1+CATALOG.tracks.length)%CATALOG.tracks.length].id;persist();syncPlayer()}};render();'''
    css = '''*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color:#231522;background:#fff7fb;min-height:100vh}.ambient{position:fixed;border-radius:999px;filter:blur(70px);opacity:.34;pointer-events:none}.ambient.one{width:390px;height:390px;background:#ff7abb;right:8%;top:-120px}.ambient.two{width:300px;height:300px;background:#ffd4e9;left:28%;bottom:5%}.app{display:grid;grid-template-columns:230px 1fr;min-height:calc(100vh - 94px);position:relative}aside{padding:32px 22px;border-right:1px solid #f1dce8;background:rgba(255,255,255,.82);backdrop-filter:blur(18px)}.brand{font-size:24px;font-weight:800;letter-spacing:-1px;margin-bottom:40px}.brand span{display:inline-grid;place-items:center;width:36px;height:36px;margin-right:9px;color:white;border-radius:12px;background:linear-gradient(135deg,#ff2d8d,#ff73b7);box-shadow:0 10px 25px #ff2d8d45}nav{display:grid;gap:8px}nav button{border:0;background:transparent;text-align:left;padding:12px 14px;border-radius:12px;color:#765f70;font-weight:700;cursor:pointer}nav button.active,nav button:hover{background:#ffe5f1;color:#d90c68}.demo{margin-top:48px;padding:12px;border:1px solid #ffc7df;background:#fff5fa;color:#c51b66;border-radius:12px;font-size:10px;font-weight:900;letter-spacing:.08em}.fine{font-size:11px;color:#9d8595;line-height:1.5}main{padding:34px 48px 130px;max-width:1320px;width:100%}header{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}header small,.artist-detail small,.detail small{color:#d81a6d;font-weight:900;letter-spacing:.13em}h1{font-size:38px;margin:5px 0;letter-spacing:-1.5px}.profile{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;color:white;font-weight:800;background:linear-gradient(135deg,#222,#7c3a63)}.hero{min-height:310px;border-radius:28px;padding:42px;display:flex;justify-content:space-between;align-items:center;color:white;background:linear-gradient(120deg,#ff167c,#ff65ae 52%,#ffb1d3);box-shadow:0 28px 60px #ec3b8f30;overflow:hidden}.hero h2{font-size:52px;line-height:.95;margin:13px 0;letter-spacing:-3px}.hero p{max-width:420px}.hero button,.detail button{border:0;border-radius:999px;background:#20121e;color:white;padding:13px 20px;font-weight:800}.hero-disc{width:220px;height:220px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle at 50%,#fff 0 8%,#301627 9% 13%,#ffdae9 14% 15%,#ad0f55 16% 23%,#ff8ec0 24% 26%,#70103c 27% 100%);box-shadow:-30px 35px 70px #7f06386b;transform:rotate(-12deg)}.hero-disc i{font-size:40px}.section-head{display:flex;justify-content:space-between;align-items:center;margin:34px 0 14px}.section-head h2{margin:0;font-size:23px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.cover-card,.playlist,.artist-card{background:rgba(255,255,255,.82);border:1px solid #f4deea;border-radius:18px;padding:12px;box-shadow:0 14px 40px #4a12320b;cursor:pointer}.cover{aspect-ratio:1;border-radius:14px;display:grid;place-items:center;color:#fff;font-size:36px;margin-bottom:11px}.cover.large{width:230px}.cover-card strong,.cover-card small,.playlist strong,.playlist small,.artist-card strong,.artist-card small{display:block}.cover-card small,.playlist small,.artist-card small{color:#90768a;margin-top:4px}.playlist>div{height:95px;border-radius:13px;display:grid;place-items:center;font-size:30px;color:white;background:linear-gradient(145deg,#ff3c93,#9b4dff)}.artist-card{text-align:center}.artist-card>div{width:86px;height:86px;border-radius:50%;margin:4px auto 12px;display:grid;place-items:center;color:white;font-size:30px;font-weight:900;background:linear-gradient(145deg,var(--accent),#ffd5e8)}.search{display:flex;gap:12px;align-items:center;padding:14px 18px;background:white;border:1px solid #f0d9e6;border-radius:16px;box-shadow:0 12px 35px #4a12320b}.search input{width:100%;border:0;outline:0;font-size:17px;background:transparent}.track{grid-column:1/-1;border:0;border-bottom:1px solid #f4e1eb;background:rgba(255,255,255,.8);display:grid;grid-template-columns:42px 1fr 42px 55px;align-items:center;text-align:left;padding:12px;border-radius:10px;cursor:pointer}.track span strong,.track span small{display:block}.track small{color:#92798b}.track i{color:#ee1f7b;font-size:20px}.track time{color:#8c7487}.library-hero,.detail{display:flex;gap:28px;align-items:center;padding:28px;border-radius:24px;background:linear-gradient(125deg,#fff,#ffe1ef)}.library-hero>span{font-size:80px;color:#ee2c83}.library-hero h2,.detail h2,.artist-detail h2{font-size:44px;margin:5px 0}.artist-detail{padding:42px;border-radius:26px;color:white;background:linear-gradient(130deg,var(--accent),#231522)}.artist-detail>div{width:82px;height:82px;border-radius:50%;display:grid;place-items:center;background:#ffffff2c;font-size:34px;font-weight:900}.back{border:0;background:transparent;color:#c71864;font-weight:800;margin-bottom:16px}.empty{grid-column:1/-1;padding:30px;border:1px dashed #efbdd4;border-radius:14px;color:#8d7385;text-align:center}.player{position:fixed;z-index:5;left:0;right:0;bottom:0;height:94px;display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;padding:14px 28px;background:rgba(255,255,255,.9);border-top:1px solid #f0d9e6;backdrop-filter:blur(22px)}.now{display:flex;align-items:center;gap:12px}.now span,.now strong{display:block}.now span{font-size:12px;color:#8d7587}.mini-cover{width:50px;height:50px;border-radius:10px;background:linear-gradient(135deg,#ff2d8d,#ffb3d5)}.now button,.transport button{border:0;background:transparent;font-size:20px}.transport{text-align:center}.transport>div{display:flex;justify-content:center;gap:16px}.transport input{width:100%}.transport .play{width:42px;height:42px;border-radius:50%;background:#231522;color:white}.volume{display:flex;justify-content:flex-end;gap:8px}@media(max-width:900px){.app{grid-template-columns:1fr}aside{position:static;border-right:0}.brand{margin-bottom:15px}nav{grid-template-columns:repeat(3,1fr)}.demo,.fine{display:none}main{padding:24px 20px 130px}.grid{grid-template-columns:repeat(2,1fr)}.hero-disc{display:none}.player{grid-template-columns:1fr 1fr}.volume{display:none}}'''
    product_py = "CATALOG = " + repr(catalog) + "\n\ndef search(query):\n    q=query.casefold().strip()\n    return [t for t in CATALOG['tracks'] if q in (t['title']+' '+t['artist']+' '+t['album']).casefold()]\n"
    test_py = '''import unittest\nfrom product import CATALOG, search\nclass MusicPrototypeTests(unittest.TestCase):\n    def test_catalog_is_fictitious_and_complete(self):\n        self.assertGreaterEqual(len(CATALOG["artists"]),4);self.assertGreaterEqual(len(CATALOG["albums"]),4);self.assertGreaterEqual(len(CATALOG["tracks"]),6)\n    def test_search(self): self.assertEqual(search("Naya")[0]["artist"],"Naya Sol")\n    def test_unique_ids(self):\n        ids=[x["id"] for k in CATALOG for x in CATALOG[k]];self.assertEqual(len(ids),len(set(ids)))\nif __name__=="__main__": unittest.main()\n'''
    return {"prototype.html": html_doc, "prototype.js": js, "style.css": css, "product.py": product_py, "app.py": '"""Local-only generated music prototype; no external API."""\n', "test_product.py": test_py}


def _generic_files(spec, project_id, version):
    name = html.escape(spec["name"])
    spec_json = json.dumps(spec, ensure_ascii=False)
    cards = "".join(f"<article><span>{i+1:02d}</span><h2>{html.escape(page)}</h2><p>{html.escape(spec['features'][i % len(spec['features'])])}</p></article>" for i, page in enumerate(spec["pages"]))
    nav = "".join(f"<button data-page=\"{i}\">{html.escape(page)}</button>" for i, page in enumerate(spec["navigation"]))
    html_doc = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name}</title><link rel="stylesheet" href="style.css"><script src="prototype.js" defer></script></head><body><header><strong>{name}</strong><span>DÉMO LOCALE — DONNÉES FICTIVES</span></header><nav>{nav}</nav><main><small>{html.escape(spec['application_type']).upper()}</small><h1>{html.escape(spec['description'])}</h1><p>{html.escape(spec['target_user'])}</p><section>{cards}</section><div id="detail"></div></main></body></html>'''
    storage_key = f"atlas:{project_id}:v{version}:{spec['application_type']}"
    js = f'''const SPEC={spec_json};const STORAGE_KEY={json.dumps(storage_key)};let state=JSON.parse(localStorage.getItem(STORAGE_KEY)||'{{"visits":0}}');state.visits+=1;localStorage.setItem(STORAGE_KEY,JSON.stringify(state));document.querySelectorAll("[data-page]").forEach((b,i)=>b.onclick=()=>document.querySelector("#detail").innerHTML=`<article class="focus"><h2>${{SPEC.pages[i]||SPEC.pages[0]}}</h2><p>${{SPEC.interactions.join(" · ")}}</p><strong>${{SPEC.storage}}</strong></article>`);'''
    css = '''*{box-sizing:border-box}body{margin:0;font-family:system-ui;background:%s;color:#18202b}header{display:flex;justify-content:space-between;padding:24px 6vw;background:white;border-bottom:1px solid #dfe5ee}header strong{font-size:24px;color:%s}header span,small{font-size:11px;font-weight:800;letter-spacing:.1em}nav{padding:16px 6vw;display:flex;gap:10px}button{border:0;padding:10px 15px;border-radius:10px;background:%s;color:white}main{padding:35px 6vw}h1{max-width:800px;font-size:42px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;margin-top:30px}article{padding:24px;border-radius:18px;background:white;box-shadow:0 12px 35px #22334412}article span{color:%s;font-weight:900}.focus{margin-top:22px;border-left:5px solid %s}''' % (spec['theme']['background'],spec['theme']['primary'],spec['theme']['primary'],spec['theme']['accent'],spec['theme']['accent'])
    product_py = "SPECIFICATION = " + repr(spec) + "\n"
    test_py = '''import unittest\nfrom product import SPECIFICATION\nclass GeneratedPrototypeTests(unittest.TestCase):\n    def test_complete_specification(self):\n        required={"name","description","application_type","target_user","pages","navigation","features","entities","interactions","theme","storage","api","test_criteria"};self.assertTrue(required.issubset(SPECIFICATION))\n    def test_pages_and_features(self): self.assertTrue(SPECIFICATION["pages"]);self.assertTrue(SPECIFICATION["features"])\nif __name__=="__main__": unittest.main()\n'''
    return {"prototype.html": html_doc, "prototype.js": js, "style.css": css, "product.py": product_py, "app.py": '"""Local-only generated prototype; no external API."""\n', "test_product.py": test_py}


def build_files(spec, project_id, version):
    files = _music_files(spec, project_id, version) if spec["application_type"] == "music-library" else _generic_files(spec, project_id, version)
    files["specification.json"] = json.dumps(spec, ensure_ascii=False, indent=2)
    return files


def validate_specification(spec):
    missing = [key for key in REQUIRED_SPEC_FIELDS if key not in spec]
    if missing:
        raise ValueError("Spécification incomplète : " + ", ".join(missing))
    if not spec["pages"] or not spec["features"] or not spec["entities"]:
        raise ValueError("Spécification sans contenu métier")
    return True
