"""Local-only QueuePilot API; standard library only, no outgoing requests."""
import http.server, json, pathlib, os, secrets, hmac
from urllib.parse import urlsplit
import product

BASE = pathlib.Path(__file__).parent
TOKEN = secrets.token_urlsafe(32)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def context(self):
        return pathlib.Path(os.environ.get('QUEUEPILOT_DB', 'queuepilot.sqlite')), urlsplit(self.path).path
    def trusted(self):
        port=self.server.server_address[1]
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')
    def send(self, code, data, mime='application/json'):
        if not isinstance(data, bytes): data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code)
        for k,v in {'Content-Type':mime,'Content-Length':str(len(data)), 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if not self.trusted(): return self.send(403,{'error':'Host refusé'})
        try:
            db, path=self.context()
            if path=='/api/session': return self.send(200,{'token':TOKEN})
            if path=='/api/requests': return self.send(200,{'requests':product.listing(str(db)), 'synthetic':True})
            files={'/':'prototype.html','/prototype.js':'prototype.js','/style.css':'style.css'}
            if path not in files: return self.send(404,{'error':'Introuvable'})
            mime={'/':'text/html; charset=utf-8','/prototype.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path]
            return self.send(200,(BASE/files[path]).read_bytes(),mime)
        except (ValueError,KeyError): self.send(404,{'error':'Projet introuvable'})
    def do_POST(self):
        expected='http://'+self.headers.get('Host','')
        if not self.trusted() or self.headers.get('Origin')!=expected or not hmac.compare_digest(self.headers.get('X-Atlas-Token',''),TOKEN):
            return self.send(403,{'error':'Origine ou jeton refusé'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=4096 or self.headers.get('Content-Type')!='application/json': raise ValueError('Format invalide')
            self.connection.settimeout(5)
            data=json.loads(self.rfile.read(n)); db,path=self.context()
            if path=='/api/requests': return self.send(201,product.create(str(db),data))
            if path.startswith('/api/requests/'):
                return self.send(200,product.update(str(db),path.rsplit('/',1)[1],data))
            self.send(404,{'error':'Introuvable'})
        except (ValueError,TypeError): self.send(400,{'error':'Données invalides : vérifier client, titre, priorité et statut.'})
        except KeyError: self.send(404,{'error':'Demande introuvable'})

if __name__=='__main__':
    product.seed(os.environ.get('QUEUEPILOT_DB','queuepilot.sqlite'))
    http.server.ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','8767'))),Handler).serve_forever()
