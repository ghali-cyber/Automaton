#!/usr/bin/python3
"""Human-operated client, no credentials or direct code execution."""
import argparse,http.client,json,socket
class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.connect('/run/atlas-business/tools.sock')
p=argparse.ArgumentParser()
p.add_argument('action',choices=['web_search','web_read','workspace_list','workspace_read','workspace_write','workspace_exec','n8n_status'])
for field in ['query','url','path','content','command']:p.add_argument('--'+field)
args=vars(p.parse_args()); action=args.pop('action')
c=Connection('localhost',timeout=45)
c.request('POST','/tools',json.dumps({'action':action,'args':{k:v for k,v in args.items() if v is not None}}),{'Content-Type':'application/json'})
r=c.getresponse();print(json.dumps(json.loads(r.read()),ensure_ascii=False,indent=2));c.close()
raise SystemExit(0 if r.status==200 else 1)
