#!/usr/bin/python3
"""Atlas phase-one broker. Root-owned policy; never evaluates model code in host context."""
import datetime, html, http.client, http.server, ipaddress, json, os, pathlib, re, sys
import resource, selectors, signal, socket, socketserver, ssl, stat, subprocess, threading, time, tarfile, uuid
from urllib.parse import urlsplit, urlencode, unquote, quote
# Python's isolated mode deliberately removes the script directory from
# sys.path. Re-add only this fixed, root-owned deployment directory so the
# broker can load its controlled Web gateway without weakening isolation.
sys.path.insert(0, '/opt/atlas-business')
import web_gateway

ROOT = pathlib.Path('/srv/atlas-workspace')
SOCKET = '/run/atlas-business/tools.sock'
NODE = '/opt/atlas-business/node'
MAX_OUTPUT = 64000
LAST_WEB = 0.0
ALLOWED = {'example.com', 'docs.python.org', 'developer.mozilla.org', 'en.wikipedia.org', 'fr.wikipedia.org'}
SNAPSHOTS = pathlib.Path('/var/lib/atlas-business-snapshots')

def checkpoint():
    # Fail closed rather than pruning recovery data without a human decision.
    entries=[]; estimate=10240
    for directory, folders, files in os.walk(ROOT, followlinks=False):
        for name in folders+files:
            p=pathlib.Path(directory)/name
            meta=p.lstat()
            relative=str(p.relative_to(ROOT))
            estimate += 4096 + len(relative.encode('utf-8'))*4
            if stat.S_ISREG(meta.st_mode): estimate += meta.st_size
            if estimate > 64*1024*1024: raise ValueError('Workspace exceeds recovery snapshot budget; human review required')
            entries.append((p,relative))
    used=sum(p.stat().st_size for p in SNAPSHOTS.iterdir() if p.is_file())
    if used+estimate > 256*1024*1024: raise ValueError('Recovery storage full; human review required, no snapshots automatically deleted')
    target=SNAPSHOTS/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex+'.tar')
    with tarfile.open(target,'x',dereference=False) as archive:
        for p,relative in entries: archive.add(p,arcname=relative,recursive=False)
    return target.name

def text(value, limit=16000):
    if not isinstance(value, str) or not value or len(value) > limit or '\x00' in value:
        raise ValueError('Invalid or oversized string')
    return value

def path(value, directory=False):
    value = text(value)
    p = pathlib.PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value:
        raise ValueError('Relative workspace paths only')
    current = ROOT
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlinks are not allowed')
    if current == ROOT and not directory:
        raise ValueError('File path required')
    return current

def safe_read(value, binary=False):
    p = path(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        meta = os.fstat(f.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size > MAX_OUTPUT:
            raise ValueError('Only small regular files are readable')
        data = f.read(MAX_OUTPUT + 1)
    return data if binary else data.decode('utf-8')

def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (8*1024*1024, 8*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def execute(command):
    command = text(command)
    checkpoint_id = checkpoint()
    args = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL',
      '--clearenv', '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
      '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
      '--ro-bind', NODE, '/opt/node', '--proc', '/proc', '--dev', '/dev',
      '--size', '67108864', '--tmpfs', '/tmp', '--dir', '/home', '--dir', '/etc',
      '--bind', str(ROOT), '/workspace', '--chdir', '/workspace',
      '--setenv', 'PATH', '/opt/node/bin:/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
      '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'TMPDIR', '/tmp',
      '--', '/bin/bash', '--noprofile', '--norc', '-c', command]
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, env={'PATH':'/usr/bin:/bin'}, start_new_session=True, preexec_fn=limits)
    output = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(p.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + 25
    reason = None
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                reason = 'timeout'; break
            for key, _ in selector.select(.1):
                chunk = os.read(key.fd, 4096)
                if not chunk:
                    selector.unregister(key.fileobj); continue
                output.extend(chunk)
                if len(output) > MAX_OUTPUT:
                    reason = 'output_limit'; break
            if reason: break
        if reason:
            os.killpg(p.pid, signal.SIGKILL)
        p.wait(timeout=3)
    finally:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL); p.wait()
        selector.close(); p.stdout.close()
    return {'exit_code':p.returncode, 'limit':reason, 'output':output[:MAX_OUTPUT].decode('utf-8','replace'), 'recovery_snapshot':checkpoint_id}

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=12, context=ssl.create_default_context())
        self.address = address
    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)

def fetch(url, search=False):
    global LAST_WEB
    now = time.monotonic()
    if now - LAST_WEB < 2: raise ValueError('Web rate limit: wait two seconds')
    u = urlsplit(text(url, 2000))
    if u.scheme != 'https' or u.username or u.password or u.port not in (None,443) or u.fragment:
        raise ValueError('Plain HTTPS URLs only, without credentials, fragment or custom port')
    if search:
        if u.hostname != 'en.wikipedia.org' or u.path != '/w/api.php': raise ValueError('Invalid search endpoint')
    elif u.hostname not in ALLOWED or u.query:
        raise ValueError('Domain/query not approved; human review required')
    addresses = {item[4][0] for item in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('Private, loopback, reserved and metadata addresses blocked')
    LAST_WEB = now
    c = PinnedHTTPS(u.hostname, sorted(addresses, key=lambda a:(ipaddress.ip_address(a).version,a))[0])
    try:
        c.request('GET', (u.path or '/') + ('?' + u.query if u.query else ''),
                  headers={'User-Agent':'Atlas-Local-Research/1.0', 'Accept':'text/html,text/plain,application/json'})
        r = c.getresponse()
        if r.status != 200: raise ValueError('HTTP ' + str(r.status) + '; redirects/paywalls are not followed')
        if r.getheader('Content-Type','').split(';')[0] not in ('text/html','text/plain','application/json','application/xhtml+xml','text/xml','application/xml','application/rss+xml'):
            raise ValueError('Unsupported content type')
        data = r.read(200001)
        if len(data) > 200000: data = data[:200000]
        source = data.decode('utf-8','replace')
        if search:
            results=[{'title':item['title'],'url':'https://en.wikipedia.org/wiki/'+quote(item['title'].replace(' ','_')),'description':html.unescape(re.sub('<[^>]+>',' ',item['snippet']))} for item in json.loads(source).get('query',{}).get('search',[])[:10]]
            if not results: raise ValueError('Search returned no verifiable results')
            return {'untrusted':True,'provider':'Wikipedia (general web search not yet enabled)','url':url,'results':results}
        links = re.findall(r'href=[\"\x27]([^\"\x27]+)', source)[:60]
        source = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', source, flags=re.S|re.I)
        source = html.unescape(re.sub('<[^>]+>', ' ', source))
        return {'untrusted':True, 'url':url, 'text':re.sub(r'\s+', ' ', source)[:18000], 'links':links}
    finally: c.close()

def dispatch(action, args):
    if action == 'workspace_exec': return execute(args.get('command'))
    if action == 'workspace_read': return {'content':safe_read(args.get('path'))}
    if action == 'workspace_list':
        p = path(args.get('path','.'), True)
        return {'entries':[{'name':x.name,'symlink':x.is_symlink()} for x in list(p.iterdir())[:200]]}
    if action == 'workspace_write':
        content = args.get('content')
        if not isinstance(content,str) or len(content.encode('utf-8')) > MAX_OUTPUT: raise ValueError('File too large')
        p = path(args.get('path')); checkpoint_id=checkpoint(); p.parent.mkdir(parents=True,exist_ok=True)
        fd = os.open(p, os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK, 0o600)
        with os.fdopen(fd,'wb') as f:
            info=os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise ValueError('Only regular files')
            f.truncate(0); f.write(content.encode('utf-8'))
        return {'written':args['path'], 'bytes':len(content.encode('utf-8')), 'recovery_snapshot':checkpoint_id}
    if action == 'web_read': return web_gateway.fetch(args.get('url'))
    if action == 'web_search':
        return web_gateway.search_web(args.get('query'))
    if action == 'n8n_status':
        c=http.client.HTTPConnection('127.0.0.1',5678,timeout=3)
        try:
            c.request('GET','/healthz'); r=c.getresponse(); r.read(2048)
            return {'available':r.status == 200,'status':r.status,'workflows_enabled':False}
        except OSError: return {'available':False,'workflows_enabled':False}
        finally: c.close()
    raise ValueError('Unknown or disabled action')

LOCK=threading.Lock()
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        action='invalid'; success=False
        try:
            if self.path != '/tools': raise ValueError('Invalid endpoint')
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=100000: raise ValueError('Request size')
            self.connection.settimeout(5)
            request=json.loads(self.rfile.read(n)); action=request['action']; args=request.get('args',{})
            if not isinstance(args,dict) or not isinstance(action,str): raise ValueError('Invalid request')
            with LOCK: result=dispatch(action,args)
            status=200; success=True
        except Exception as e: result={'error':str(e)[:400]}; status=400
        data=json.dumps(result,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        print(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':action[:40],'ok':success}),flush=True)

class UnixServer(socketserver.UnixStreamServer): allow_reuse_address=True

class Preview(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        try:
            u=urlsplit(self.path)
            if u.query or u.fragment: raise ValueError('No query')
            requested=unquote(u.path).lstrip('/') or 'index.html'
            with LOCK: body=safe_read('site/'+requested,True)
            ext=pathlib.Path(requested).suffix
            content={'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.json':'application/json','.txt':'text/plain'}.get(ext)
            if not content: raise ValueError('Unsupported file')
            self.send_response(200); self.send_header('Content-Type',content)
            self.send_header('Content-Security-Policy',"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        except Exception: self.send_error(404)

if __name__ == '__main__':
    os.umask(0o077)
    if os.path.exists(SOCKET): os.unlink(SOCKET)
    server=UnixServer(SOCKET,Handler); os.chmod(SOCKET,0o660)
    preview=http.server.HTTPServer(('127.0.0.1',8765),Preview)
    threading.Thread(target=preview.serve_forever,daemon=True).start()
    print('Atlas business broker ready; loopback preview 8765',flush=True)
    server.serve_forever()
