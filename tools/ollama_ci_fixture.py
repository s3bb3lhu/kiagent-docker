"""In-process Ollama protocol fixture, only for disposable CI; no model downloads."""
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

class Fixture:
    def __init__(self):
        self.requests=[];owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,data):
                payload=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def do_GET(self):
                owner.requests.append((self.path,None))
                if self.path=='/api/version':self.send({'version':'CI fixture only'})
                elif self.path=='/api/tags':self.send({'models':[{'name':'qwen3:0.6b','size':523000000}]})
                else:self.send_error(404)
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));owner.requests.append((self.path,data))
                if self.path!='/api/chat':self.send_error(403);return
                self.send({'done':True,'message':{'content':'{"intent":"answer","package":"","answer":"Local CI answer"}'}})
        self.server=ThreadingHTTPServer(('127.0.0.1',11434),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def verify(self):
        assert all(path in ('/api/version','/api/tags','/api/chat') for path,data in self.requests)
        for path,body in self.requests:
            if path=='/api/chat':
                assert 'keep_alive' not in body and 'num_thread' not in body['options']
                assert body['options']['num_ctx']==2048 and body['options']['num_predict']<=512
