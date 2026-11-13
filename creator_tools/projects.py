"""Local non-destructive projects. SQLite transactions + optimistic revisions."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import uuid
from creator_tools import editing

MAX_UPLOAD = 256 * 1024 * 1024

class Conflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):
        raise ValueError('Invalid ID')
    return value


def _name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>120:
        raise ValueError('Name must be 1–120 characters')
    return name.strip()


class Store:
    def __init__(self, root):
        self.root=Path(root).expanduser().resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        for d in ('media','exports'):(self.root/d).mkdir(exist_ok=True)
        self.lock=threading.RLock()
        self.path=self.root/'studio.sqlite3'
        with self.db() as c:
            c.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
    @contextmanager
    def db(self):
        with self.lock:
            c=sqlite3.connect(self.path,timeout=30)
            try:
                c.execute('BEGIN IMMEDIATE')
                yield c
                c.commit()
            except Exception:
                c.rollback();raise
            finally:c.close()
    def _document(self,c,identifier):
        row=c.execute('SELECT document FROM projects WHERE id=?',(_id(identifier),)).fetchone()
        if not row:raise ValueError('Project not found')
        return json.loads(row[0])
    def _view(self,d):
        s=d['versions'][d['chain'][d['cursor']]]
        return {'id':d['id'],'name':s['name'],'plan':deepcopy(s['plan']),
                'revision':d['revision'],'updated_at':d['updated_at'],
                'history':[{'revision':v['revision'],'label':v['label'],'created_at':v['created_at']} for v in d['versions']],
                'can_undo':d['cursor']>0,'can_redo':d['cursor']<len(d['chain'])-1}
    def create(self,name):
        name=_name(name);identifier=uuid.uuid4().hex;t=now()
        plan={'version':1,'clips':[],'width':1280,'height':720,'fit':'contain','mute':False,'volume':1}
        d={'id':identifier,'revision':1,'updated_at':t,'cursor':0,'chain':[0],
           'versions':[{'revision':1,'name':name,'plan':plan,'created_at':t,'label':'Created'}]}
        with self.db() as c:c.execute('INSERT INTO projects VALUES (?,?)',(identifier,json.dumps(d)))
        return self._view(d)
    def get(self,identifier):
        with self.db() as c:return self._view(self._document(c,identifier))
    def projects(self):
        with self.db() as c:
            rows=[self._view(json.loads(r[0])) for r in c.execute('SELECT document FROM projects')]
        return sorted([dict((k,r[k]) for k in ('id','name','revision','updated_at')) for r in rows],key=lambda r:r['updated_at'],reverse=True)
    def _validate(self,plan):
        plan=json.loads(json.dumps(plan,allow_nan=False))
        if not isinstance(plan,dict) or set(plan)-editing._TOP_KEYS:
            raise ValueError('Invalid or unknown edit-plan fields')
        if not isinstance(plan.get('clips'),list):raise ValueError('clips must be a list')
        allowed={a['path'] for a in self.assets()}
        for clip in plan['clips']:
            if not isinstance(clip,dict) or clip.get('path') not in allowed:
                raise ValueError('Import the source into this Studio before using it in a project')
        if any(plan.get(k) is not None for k in ('subtitles','bgm')) or plan.get('retime_subtitles') or plan.get('burn_subtitles'):
            raise ValueError('Studio subtitle/bgm import is not implemented; use the local CLI')
        if plan['clips']:
            editing.validate_plan(plan)
        else:
            if type(plan.get('version')) is not int or plan['version']!=1:raise ValueError('Invalid version')
            editing._even_dim(plan.get('width'),'width');editing._even_dim(plan.get('height'),'height')
            if plan.get('fit','contain') not in ('contain','cover'):raise ValueError('Invalid framing')
            if not isinstance(plan.get('mute',False),bool):raise ValueError('Invalid mute')
            if not 0<=editing._finite_number(plan.get('volume',1),'volume')<=2:raise ValueError('Invalid volume')
            for k in ('fade_in','fade_out'):
                if editing._finite_number(plan.get(k,0),k)!=0:raise ValueError('Add clips before setting fades')
        return plan
    def _expect(self,d,revision):
        if type(revision) is not int or revision!=d['revision']:
            raise Conflict('This project changed in another tab. Reload before saving.')
    def save(self,identifier,plan,expected_revision,name=None,label='Edit'):
        plan=self._validate(plan)
        with self.db() as c:
            d=self._document(c,identifier);self._expect(d,expected_revision)
            current=self._view(d)
            name=_name(current['name'] if name is None else name)
            if not isinstance(label,str) or len(label)>200:raise ValueError('Invalid revision label')
            d['revision']+=1;d['updated_at']=now()
            d['versions'].append({'revision':d['revision'],'name':name,'plan':plan,'created_at':d['updated_at'],'label':label})
            d['chain']=d['chain'][:d['cursor']+1]+[len(d['versions'])-1]
            d['cursor']=len(d['chain'])-1
            c.execute('UPDATE projects SET document=? WHERE id=?',(json.dumps(d,allow_nan=False),identifier))
        return self._view(d)
    def _move(self,identifier,expected_revision,delta):
        with self.db() as c:
            d=self._document(c,identifier);self._expect(d,expected_revision)
            cursor=d['cursor']+delta
            if not 0<=cursor<len(d['chain']):raise ValueError('No revision to undo/redo')
            d['cursor']=cursor;d['revision']+=1;d['updated_at']=now()
            c.execute('UPDATE projects SET document=? WHERE id=?',(json.dumps(d),identifier))
        return self._view(d)
    def undo(self,identifier,expected_revision):return self._move(identifier,expected_revision,-1)
    def redo(self,identifier,expected_revision):return self._move(identifier,expected_revision,1)
    def import_asset(self,name,data):
        name=_name(name)
        suffix=Path(name).suffix.lower()
        if suffix not in ('.mp4','.mov','.m4v','.webm','.mkv','.avi'):
            raise ValueError('Import MP4, MOV, M4V, WebM, MKV or AVI video')
        if not isinstance(data,bytes) or not 0<len(data)<=MAX_UPLOAD:
            raise ValueError('Video must be nonempty and no larger than 256 MiB')
        identifier=uuid.uuid4().hex;path=self.root/'media'/(identifier+suffix)
        try:
            with path.open('xb') as f:f.write(data)
            meta=editing.probe(str(path))
            if meta['width']<=0 or meta['height']<=0 or meta['duration']<=0:
                raise ValueError('File must contain a playable video')
            row={'id':identifier,'name':name,**meta,'url':'/media/'+identifier,'kind':'source',
                 'sha256':hashlib.sha256(data).hexdigest(),'created_at':now()}
            with self.db() as c:c.execute('INSERT INTO assets VALUES (?,?)',(identifier,json.dumps(row,allow_nan=False)))
            return row
        except Exception:
            path.unlink(missing_ok=True);raise
    def assets(self):
        with self.db() as c:
            return [a for r in c.execute('SELECT document FROM assets') if (a:=json.loads(r[0]))['kind']=='source']
    def asset(self,identifier):
        with self.db() as c:
            row=c.execute('SELECT document FROM assets WHERE id=?',(_id(identifier),)).fetchone()
        if not row:raise ValueError('Media not found')
        a=json.loads(row[0]);p=Path(a['path']).resolve()
        if not p.is_relative_to(self.root) or not p.is_file():raise ValueError('Media is missing or outside Studio')
        return a
    def register_export(self,path,name):
        path=Path(path).resolve()
        if not path.is_relative_to(self.root/'exports'):raise ValueError('Invalid export path')
        meta=editing.probe(str(path));identifier=uuid.uuid4().hex
        row={'id':identifier,'name':name,**meta,'url':'/media/'+identifier,'kind':'export','created_at':now()}
        with self.db() as c:c.execute('INSERT INTO assets VALUES (?,?)',(identifier,json.dumps(row)))
        return row
    def put_job(self,job):
        with self.db() as c:c.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(_id(job['id']),json.dumps(job,allow_nan=False)))
    def jobs(self):
        with self.db() as c:rows=[json.loads(r[0]) for r in c.execute('SELECT document FROM jobs')]
        return sorted(rows,key=lambda r:r['created_at'],reverse=True)
    def recover_jobs(self):
        for job in self.jobs():
            if job['status'] in ('queued','running'):
                job.update(status='failed',error='Studio stopped before this render completed. Render again.')
                self.put_job(job)
