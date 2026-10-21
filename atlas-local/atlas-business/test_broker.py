import http.client, json, socket, sys, time, unittest
sys.path.insert(0,'/opt/atlas-business')
import broker

class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.connect('/run/atlas-business/tools.sock')

def call(action, **args):
    c=UnixHTTP('localhost',timeout=40)
    c.request('POST','/tools',json.dumps({'action':action,'args':args}),{'Content-Type':'application/json'})
    r=c.getresponse(); result=json.loads(r.read()); c.close()
    if r.status != 200: raise ValueError(result)
    return result

class BusinessTests(unittest.TestCase):
    def test_01_files(self):
        call('workspace_write',path='checks/hello.txt',content='Atlas local test')
        self.assertEqual(call('workspace_read',path='checks/hello.txt')['content'],'Atlas local test')
        self.assertIn('hello.txt',[e['name'] for e in call('workspace_list',path='checks')['entries']])
        for p in ['/etc/passwd','../state.db','a/../../wallet.json','a\\b']:
            with self.assertRaises(ValueError): call('workspace_read',path=p)
    def test_02_isolation(self):
        code="""import os, socket, pathlib
assert not pathlib.Path('/home/atlas-owner').exists()
assert not pathlib.Path('/mnt/c').exists()
assert not pathlib.Path('/var/lib/automaton-local').exists()
assert not pathlib.Path('/run/atlas-business/tools.sock').exists()
assert not pathlib.Path('/etc/shadow').exists()
assert set(os.environ) <= {'PATH','HOME','LANG','TMPDIR','PWD','SHLVL','_','LC_CTYPE'}
for host,port in [('1.1.1.1',443),('127.0.0.1',11434),('127.0.0.1',5678),('127.0.0.1',8765)]:
    try:
        s=socket.create_connection((host,port),.4)
    except OSError: pass
    else:
        s.close(); raise AssertionError('network escape')
try: pathlib.Path('/usr/atlas-write-test').write_text('blocked')
except OSError: pass
else: raise AssertionError('runtime writable')
print('isolation checks passed')
"""
        call('workspace_write',path='checks/isolation.py',content=code)
        result=call('workspace_exec',command='python3 checks/isolation.py')
        self.assertEqual(result['exit_code'],0,result)
        self.assertIn('isolation checks passed',result['output'])
    def test_03_links(self):
        result=call('workspace_exec',command='ln -sfn /etc/passwd checks/escape; mkfifo checks/fifo 2>/dev/null || true')
        self.assertEqual(result['exit_code'],0,result)
        for p in ['checks/escape','checks/fifo']:
            with self.assertRaises(ValueError): call('workspace_read',path=p)
            with self.assertRaises(ValueError): call('workspace_write',path=p,content='no')
    def test_04_site_and_tests(self):
        page='<!doctype html><html lang="fr"><meta charset="utf-8"><title>Atlas local</title><style>body{font:20px system-ui;max-width:800px;margin:80px auto;background:#101827;color:#e2e8f0}strong{color:#5eead4}</style><h1>Atlas — laboratoire local</h1><p>Prototype de micro-SaaS sans compte, sans paiement, sans envoi externe.</p><strong>Première couche outils opérationnelle.</strong></html>'
        call('workspace_write',path='site/index.html',content=page)
        node="""const http=require('node:http');
const assert=require('node:assert/strict');
const server=http.createServer((req,res)=>{res.setHeader('content-type','application/json');res.end(JSON.stringify({plan:'demo',price:0}));});
server.listen(0,'127.0.0.1',async()=>{try {const res=await fetch('http://127.0.0.1:'+server.address().port);assert.equal(res.status,200);assert.deepEqual(await res.json(),{plan:'demo',price:0});console.log('micro-SaaS API local test passed');}finally{server.close();}});
"""
        call('workspace_write',path='checks/api.cjs',content=node)
        result=call('workspace_exec',command='node checks/api.cjs')
        self.assertEqual(result['exit_code'],0,result)
        self.assertIn('API local test passed',result['output'])
        c=http.client.HTTPConnection('127.0.0.1',8765,timeout=5);c.request('GET','/');r=c.getresponse()
        self.assertEqual(r.status,200);self.assertIn('sandbox',r.getheader('Content-Security-Policy'));self.assertIn(b'Atlas',r.read());c.close()
    def test_05_blocked_web(self):
        for url in ['http://example.com','https://127.0.0.1','https://169.254.169.254','https://example.com@127.0.0.1','https://example.com:8443','https://example.com/?delete=yes','https://evil.example','file:///etc/passwd']:
            with self.assertRaises(ValueError): call('web_read',url=url)
        with self.assertRaises(ValueError): call('send_email',to='nobody')
        with self.assertRaises(ValueError): call('n8n_run',workflow='anything')
        with self.assertRaises(ValueError): call('payment',amount=1)
    def test_06_public_web(self):
        result=call('web_read',url='https://example.com/')
        self.assertTrue(result['untrusted']);self.assertIn('Example Domain',result['excerpt']);self.assertTrue(result['robots_allowed'])
        result=call('web_search',query='Python programming language official documentation')
        self.assertTrue(result['untrusted']);self.assertGreater(len(result['results']),0);self.assertEqual(result['provider'],'Atlas federated public APIs')
    def test_07_n8n(self):
        result=call('n8n_status');self.assertFalse(result['workflows_enabled'])
        print('n8n status:',result)
    def test_08_output_limit(self):
        result=call('workspace_exec',command="python3 -c 'print(\"a\"*100000)' ")
        self.assertEqual(result['limit'],'output_limit');self.assertLessEqual(len(result['output']),64000)
    def test_09_timeout(self):
        result=call('workspace_exec',command='sleep 30')
        self.assertEqual(result['limit'],'timeout')

if __name__=='__main__': unittest.main(verbosity=2)
