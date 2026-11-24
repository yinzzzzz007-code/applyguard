"""Loopback meter for the real Harness subprocess in the synthetic CLI regression."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
import json, secrets, threading


def relay(key):
    password=secrets.token_urlsafe(32)
    class Meter(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/v1/chat/completions' or self.headers.get('Authorization')!='Bearer '+password:
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<250000:raise ValueError()
                data=json.loads(self.rfile.read(length))
                if data.get('model')!='gemini-3.1-flash-lite-preview':raise ValueError()
                data['max_tokens']=min(int(data.get('max_tokens') or 1000),1000)
                data.pop('max_completion_tokens',None)
                import urllib.request
                with urllib.request.urlopen(Request('https://api.chatanywhere.tech/v1/chat/completions',json.dumps(data).encode(),
                        {'Authorization':'Bearer '+key,'Content-Type':'application/json'}),timeout=90) as upstream:
                    self.send_response(200)
                    self.send_header('Content-Type',upstream.headers['Content-Type'])
                    self.end_headers()
                    for part in upstream:
                        self.wfile.write(part);self.wfile.flush()
            except Exception:
                self.send_error(503)
    server=ThreadingHTTPServer(('127.0.0.1',0),Meter)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server,password
