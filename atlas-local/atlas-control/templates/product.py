"""QueuePilot domain and SQLite repository. Runs standalone with app.py."""
import sqlite3, uuid, datetime

def connect(path):
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, client TEXT NOT NULL, title TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL)')
    return c

def validate(data):
    if not isinstance(data, dict): raise ValueError('Objet requis')
    clean = {}
    for key, limit in [('client', 80), ('title', 200)]:
        value = data.get(key, '')
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(key + ' : texte requis, longueur maximale ' + str(limit))
        clean[key] = value.strip()
    clean['priority'] = data.get('priority', 'normal')
    clean['status'] = data.get('status', 'new')
    if clean['priority'] not in ('low', 'normal', 'high'): raise ValueError('Priorité invalide')
    if clean['status'] not in ('new', 'active', 'done'): raise ValueError('Statut invalide')
    return clean

def create(path, data):
    d = validate(data)
    d.update(id=uuid.uuid4().hex, created=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with connect(path) as c:
        c.execute('INSERT INTO requests VALUES(:id,:client,:title,:priority,:status,:created)', d)
    return d

def update(path, item_id, data):
    d = validate(data)
    with connect(path) as c:
        if not c.execute('SELECT id FROM requests WHERE id=?', (item_id,)).fetchone(): raise KeyError('Demande introuvable')
        c.execute('UPDATE requests SET client=:client,title=:title,priority=:priority,status=:status WHERE id=:id', dict(d, id=item_id))
    return dict(d, id=item_id)

def listing(path):
    with connect(path) as c:
        return [dict(r) for r in c.execute('SELECT * FROM requests ORDER BY created DESC')]

def seed(path):
    if listing(path): return
    for client, title, priority, status in [
        ('Studio Lune (fictif)', 'Préparer la maquette d’accueil', 'high', 'active'),
        ('Atelier Boréal (fictif)', 'Vérifier les contenus de démonstration', 'normal', 'new'),
        ('Maison Rivage (fictif)', 'Valider les couleurs du prototype', 'low', 'done')]:
        create(path, dict(client=client, title=title, priority=priority, status=status))
