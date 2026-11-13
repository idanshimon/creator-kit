"""Local/LAN Studio API. No cloud calls, arbitrary-path serving, or public bind."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ipaddress
import mimetypes
from pathlib import Path
import re
import secrets
import threading
import urllib.parse
import uuid
from creator_tools import editing
from creator_tools.projects import Store, Conflict, MAX_UPLOAD, now


def allowed_hosts(host,port):
    try:
        ip=ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        raise ValueError('Bind to a specific loopback or private LAN IPv4 address') from None
    networks=('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')
    if not ip.is_loopback and not any(ip in ipaddress.IPv4Network(n) for n in networks):
        raise ValueError('Public and wildcard binds are disabled; specify the LAN IP')
    return {f'{ip}:{port}'} | ({f'localhost:{port}'} if ip.is_loopback else set())


def byte_range(value,size):
    m=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not m or not size or not any(m.groups()):raise ValueError('Invalid range')
    a,b=m.groups()
    if not a:
        length=int(b)
        if length<=0:raise ValueError('Invalid suffix range')
        start=max(0,size-length);end=size-1
    else:
        start=int(a);end=min(int(b),size-1) if b else size-1
    if start>=size or end<start:raise ValueError('Unsatisfiable range')
    return start,end


class StudioServer(ThreadingHTTPServer):
    daemon_threads=True
    def enqueue(self,identifier,expected_revision,kind):
        if kind not in ('draft','final'):raise ValueError('Choose draft or final export')
        with self.queue_lock:
            if sum(j['status'] in ('queued','running') for j in self.store.jobs())>=3:
                raise Conflict('Render queue full. Wait for an export to finish.')
            project=self.store.get(identifier)
            if type(expected_revision) is not int or project['revision']!=expected_revision:
                raise Conflict('Project changed. Reload before exporting.')
            editing.validate_plan(project['plan'])
            snapshot=deepcopy(project['plan'])
            job={'id':uuid.uuid4().hex,'status':'queued','project_id':identifier,
                 'revision':project['revision'],'kind':kind,'result_url':None,'error':None,'created_at':now()}
            self.store.put_job(job)
            self.pool.submit(self.run_job,deepcopy(job),snapshot,project['name'])
            return job
    def run_job(self,job,plan,name):
        job['status']='running';self.store.put_job(job)
        try:
            output=self.store.root/'exports'/(job['id']+'.mp4')
            result=editing.render(plan,str(output),profile=job['kind'])
            asset=self.store.register_export(output,name+'-'+job['kind']+'.mp4')
            job.update(status='succeeded',result_url=asset['url'],result=result,error=None,completed_at=now())
        except Exception as e:
            job.update(status='failed',error=str(e)[:1000],completed_at=now())
        self.store.put_job(job)


class Handler(BaseHTTPRequestHandler):
    server_version='CreatorStudio/1'
    def setup(self):
        super().setup();self.connection.settimeout(30)
    def log_message(self,*args):pass
    def _trusted(self,write=False):
        hosts=self.headers.get_all('Host',[])
        allowed=self.server.allowed_hosts
        if len(hosts)!=1 or hosts[0].lower() not in allowed:return False
        origin=self.headers.get('Origin')
        if origin is not None and origin!='http://'+hosts[0].lower():return False
        if write:
            token=self.headers.get('X-CSRF-Token','')
            return secrets.compare_digest(token,self.server.csrf)
        return True
    def _headers(self,status,length,ctype,extra=None):
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(length))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers()
    def _json(self,status,value):
        b=json.dumps(value,allow_nan=False).encode()
        self._headers(status,len(b),'application/json; charset=utf-8')
        if self.command!='HEAD':self.wfile.write(b)
    def _bytes(self,limit):
        raw=self.headers.get('Content-Length','')
        if not raw.isdigit() or int(raw)>limit or int(raw)<=0:raise ValueError('Missing or oversized request body')
        b=self.rfile.read(int(raw))
        if len(b)!=int(raw):raise ValueError('Incomplete request body')
        return b
    def _body(self):
        def bad(x):raise ValueError('Non-finite JSON not allowed')
        value=json.loads(self._bytes(1024*1024),parse_constant=bad)
        if not isinstance(value,dict):raise ValueError('Expected JSON object')
        return value
    def _media(self,identifier):
        asset=self.server.store.asset(identifier);p=Path(asset['path']);size=p.stat().st_size
        status=200;start=0;end=size-1
        if 'Range' in self.headers:
            try:start,end=byte_range(self.headers['Range'],size);status=206
            except ValueError:
                self._headers(416,0,'video/mp4',{'Content-Range':f'bytes */{size}'});return
        extra={'Accept-Ranges':'bytes','Content-Disposition':"inline; filename*=UTF-8''"+urllib.parse.quote(asset['name'],safe='')}
        if status==206:extra['Content-Range']=f'bytes {start}-{end}/{size}'
        self._headers(status,end-start+1,mimetypes.guess_type(p)[0] or 'application/octet-stream',extra)
        if self.command=='HEAD':return
        with p.open('rb') as f:
            f.seek(start);left=end-start+1
            while left:
                b=f.read(min(65536,left))
                if not b:break
                self.wfile.write(b);left-=len(b)
    def _read(self,path):
        store=self.server.store
        if path=='/api/state':
            return self._json(200,{'csrf':self.server.csrf,'projects':store.projects(),'assets':store.assets(),'jobs':store.jobs()})
        match=re.fullmatch(r'/api/projects/([a-f0-9]{32})',path)
        if match:return self._json(200,store.get(match[1]))
        match=re.fullmatch(r'/api/jobs/([a-f0-9]{32})',path)
        if match:
            job=next((j for j in store.jobs() if j['id']==match[1]),None)
            return self._json(200,job) if job else self._json(404,{'error':'Job not found'})
        if path.startswith('/media/'):return self._media(path.removeprefix('/media/'))
        if path.startswith('/api/'):return self._json(404,{'error':'Endpoint not found'})
        p=(self.server.ui_dir/(path.lstrip('/') or 'index.html')).resolve()
        if not p.is_relative_to(self.server.ui_dir) or not p.is_file() or p.suffix not in ('.html','.js','.css','.svg','.png','.woff2','.ico'):
            return self._json(404,{'error':'Page not found'})
        b=p.read_bytes();self._headers(200,len(b),mimetypes.guess_type(p)[0] or 'application/octet-stream')
        if self.command!='HEAD':self.wfile.write(b)
    def _write(self,path):
        store=self.server.store
        if path=='/api/assets' and self.command=='POST':
            name=urllib.parse.unquote(self.headers.get('X-Filename',''))
            return self._json(201,store.import_asset(name,self._bytes(MAX_UPLOAD)))
        if path=='/api/projects' and self.command=='POST':
            return self._json(201,store.create(self._body().get('name')))
        match=re.fullmatch(r'/api/projects/([a-f0-9]{32})(?:/(undo|redo|render))?',path)
        if match:
            identifier,action=match.groups();body=self._body()
            revision=body.get('expected_revision')
            if self.command=='PUT' and not action:
                return self._json(200,store.save(identifier,body.get('plan'),revision,body.get('name'),body.get('label','Edit')))
            if self.command=='POST' and action in ('undo','redo'):
                return self._json(200,getattr(store,action)(identifier,revision))
            if self.command=='POST' and action=='render':
                return self._json(202,self.server.enqueue(identifier,revision,body.get('kind')))
        return self._json(404,{'error':'Endpoint not found'})
    def _route(self,write=False):
        try:
            if not self._trusted(write):return self._json(403,{'error':'Request rejected: use the Studio origin and session token'})
            path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            return self._write(path) if write else self._read(path)
        except Conflict as e:self._json(409,{'error':str(e)})
        except (ValueError,KeyError,TypeError) as e:self._json(400,{'error':str(e)[:600]})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception:
            self._json(500,{'error':'Studio operation failed. Check local files and retry.'})
    def do_GET(self):self._route()
    def do_HEAD(self):self._route()
    def do_POST(self):self._route(True)
    def do_PUT(self):self._route(True)


def create_server(root,port=4318,ui_dir=None,host='127.0.0.1'):
    allowed_hosts(host,port)
    ui=Path(ui_dir or Path(__file__).resolve().parents[1]/'studio-ui'/'dist').resolve()
    if not (ui/'index.html').is_file():raise ValueError('Build Studio UI first: cd studio-ui && npm run build')
    server=StudioServer((host,port),Handler)
    server.allowed_hosts=allowed_hosts(host,server.server_port)
    server.store=Store(root);server.store.recover_jobs()
    server.csrf=secrets.token_urlsafe(32);server.ui_dir=ui
    server.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='creator-render')
    server.queue_lock=threading.Lock()
    return server


def serve(root,port=4318,host='127.0.0.1'):
    server=create_server(root,port,host=host)
    scope='local only' if ipaddress.ip_address(host).is_loopback else 'trusted LAN access; no user login'
    print(f'Creator Studio: http://{host}:{server.server_port} ({scope})',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();server.pool.shutdown(wait=True)
