"""Loopback-only HTTP transport. No remote authentication or shell endpoint."""
from __future__ import annotations
import json
import mimetypes
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit,unquote

from .service import Workstation,display_text

ASSETS=Path(__file__).resolve().parents[1]/'ui'


def display_data(value):
    if isinstance(value,str):return display_text(value)
    if isinstance(value,list):return [display_data(v) for v in value]
    if isinstance(value,dict):return {k:display_data(v) for k,v in value.items() if k not in {'thinking','raw_response','chain_of_thought'}}
    return value


class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,service: Workstation):
        if address[0]!='127.0.0.1':raise ValueError('The workstation binds only to 127.0.0.1')
        self.service=service
        self.token=secrets.token_urlsafe(32)
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    server: LocalServer
    def log_message(self,*args):
        pass  # Request bodies, source content and tokens never enter access logs.

    def send(self,status: int,body: bytes,content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def json(self,value,status=200):
        self.send(status,json.dumps(display_data(value),default=str,ensure_ascii=False).encode())

    def authorized(self,api=False):
        port=self.server.server_port
        hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in hosts:return False
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in hosts}:return False
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return False
        return not api or secrets.compare_digest(self.headers.get('X-Reverend-Token',''),self.server.token)

    def do_GET(self):
        try:
            address=urlsplit(self.path);path=unquote(address.path)
            if not self.authorized(path.startswith('/api/')):
                self.json({'error':'Request origin or session token rejected'},403);return
            service=self.server.service
            query=parse_qs(address.query)
            if path=='/api/conversations':result=service.store.conversations()
            elif path=='/api/messages':result=service.store.messages(query.get('id',[''])[0])
            elif path=='/api/jobs':result=service.store.jobs()
            elif path.startswith('/api/jobs/'):result=service.store.job(path.rsplit('/',1)[-1])
            elif path=='/api/projects':result=service.projects()
            elif path=='/api/tasks':result=service.tasks()
            elif path.startswith('/api/tasks/'):result=service.task(path.rsplit('/',1)[-1])
            elif path.startswith('/api/artifacts/'):result=service.artifact(path.rsplit('/',1)[-1])
            elif path.startswith('/api/research/images/'):
                image=service.public_image(path.rsplit('/',1)[-1])
                self.send(200,image['content'],image['media_type']);return
            elif path=='/api/status':result=service.status()
            elif path=='/api/control-plane':result=service.control_plane()
            elif path=='/':
                html=(ASSETS/'index.html').read_text().replace('__SESSION_TOKEN__',self.server.token)
                self.send(200,html.encode(),'text/html; charset=utf-8');return
            elif path.startswith('/assets/'):
                file=ASSETS/path.removeprefix('/assets/')
                if file.is_symlink() or not file.resolve().is_relative_to(ASSETS.resolve()) or not file.is_file():
                    self.json({'error':'Asset not found'},404);return
                self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream');return
            else:self.json({'error':'Not found'},404);return
            self.json(result)
        except (ValueError,KeyError,TypeError) as exc:self.json({'error':str(exc)},400)
        except Exception:self.json({'error':'Local operation failed; check runtime availability'},500)

    def do_POST(self):
        try:
            if not self.authorized(True):
                self.json({'error':'Request origin or session token rejected'},403);return
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=65536 or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                self.json({'error':'Expected bounded JSON body'},400);return
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('Expected JSON object')
            path=urlsplit(self.path).path;service=self.server.service
            if path=='/api/chat':result=service.chat(**data)
            elif path=='/api/conversations/rename':
                if set(data)!={'id','title'}:raise ValueError('Expected conversation id and title')
                result=service.store.rename_conversation(data['id'],data['title'])
            elif path=='/api/conversations/delete':
                if set(data)!={'id'}:raise ValueError('Expected conversation id')
                result=service.store.delete_conversation(data['id'])
            elif path=='/api/develop':result=service.develop(**data)
            elif path=='/api/code/index':result=service.index_code(**data)
            elif path=='/api/research/fetch':result=service.fetch_public(**data)
            elif path=='/api/conversations':
                if not data.keys() <= {'title','privacy_mode'}:
                    raise ValueError('Invalid conversation fields')
                result={'id':service.store.create_conversation(
                    title=data.get('title','New conversation'),
                    privacy_mode=data.get('privacy_mode','normal'),
                )}
            elif path=='/api/projects':result=service.register(**data)
            elif path=='/api/knowledge':result=service.knowledge(**data)
            elif path=='/api/memory/search':result=service.memories(**data)
            elif path=='/api/memory/add':result=service.remember(**data)
            elif path=='/api/memory/archive':result=service.memory.archive(**data)
            elif path=='/api/diff':result=service.diff(**data)
            elif path.startswith('/api/cancel/'):result=service.cancel(path.rsplit('/',1)[-1])
            else:self.json({'error':'Not found'},404);return
            self.json(result)
        except (ValueError,KeyError,TypeError) as exc:self.json({'error':str(exc)},400)
        except Exception:self.json({'error':'Local operation failed; check runtime availability'},500)


def serve(port: int=8765):
    import fcntl
    from reverend.config import DATA_ROOT
    lock_path=DATA_ROOT/'runtime'/'gui.lock'
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    handle=lock_path.open('a+')
    try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('A Reverend GUI already owns this runtime directory')
    service=Workstation()
    server=LocalServer(('127.0.0.1',port),service)
    print(f'Reverend: http://127.0.0.1:{server.server_port} (local inference only)',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();service.close();handle.close()
