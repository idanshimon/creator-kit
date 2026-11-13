import importlib.util
import json
from pathlib import Path
import threading
import tempfile
import unittest
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]

class StudioHTTPTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'creator_tools'/'studio.py'
        self.assertTrue(path.exists(),'Local Studio server missing')
        spec=importlib.util.spec_from_file_location('studio',path)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        ui=self.root/'ui';ui.mkdir();(ui/'index.html').write_text('<!doctype html><title>Creator</title>')
        self.server=self.m.create_server(self.root/'data',port=0,ui_dir=ui)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.token=self.get('/api/state')[1]['csrf']
    def tearDown(self):
        if hasattr(self,'server'):
            self.server.shutdown();self.server.server_close();self.server.pool.shutdown(wait=True)
        if hasattr(self,'temp'):self.temp.cleanup()
    def request(self,path,method='GET',data=None,headers=None):
        r=urllib.request.Request(self.base+path,data=data,method=method,headers=headers or {})
        try:
            with urllib.request.urlopen(r,timeout=10) as x:return x.status,x.read(),dict(x.headers)
        except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
    def get(self,path):
        status,body,h=self.request(path);return status,json.loads(body),h
    def post(self,path,body,token=True,origin=None,method='POST'):
        headers={'Content-Type':'application/json','Origin':origin or self.base}
        if token:headers['X-CSRF-Token']=self.token
        status,body,h=self.request(path,method,json.dumps(body).encode(),headers)
        return status,json.loads(body),h
    def test_cross_origin_and_missing_token_rejected(self):
        self.assertEqual(self.post('/api/projects',{'name':'No'},token=False)[0],403)
        self.assertEqual(self.post('/api/projects',{'name':'No'},origin='https://evil.example')[0],403)
        self.assertEqual(self.server.store.projects(),[])
    def test_wrong_host_rejected(self):
        self.assertEqual(self.request('/api/state',headers={'Host':'evil.example'})[0],403)
    def test_project_save_undo_redo_and_conflict(self):
        status,p,_=self.post('/api/projects',{'name':'My edit'});self.assertEqual(status,201)
        status,q,_=self.post('/api/projects/'+p['id'],{'name':'Renamed','plan':p['plan'],'expected_revision':p['revision']},method='PUT')
        self.assertEqual(status,200)
        status,old,_=self.post('/api/projects/'+p['id']+'/undo',{'expected_revision':q['revision']})
        self.assertEqual(old['name'],'My edit')
        self.assertEqual(self.post('/api/projects/'+p['id'],{'plan':p['plan'],'expected_revision':p['revision']},method='PUT')[0],409)
        status,new,_=self.post('/api/projects/'+p['id']+'/redo',{'expected_revision':old['revision']})
        self.assertEqual(new['name'],'Renamed')
    def test_bad_upload_and_arbitrary_media_rejected(self):
        status,_,_=self.request('/api/assets','POST',b'fake',{'Origin':self.base,'X-CSRF-Token':self.token,'X-Filename':'bad.mp4'})
        self.assertEqual(status,400)
        self.assertEqual(self.get('/api/state')[1]['assets'],[])
        self.assertNotEqual(self.request('/media/../../etc/passwd')[0],200)
    def test_range_parser(self):
        self.assertEqual(self.m.byte_range('bytes=2-4',10),(2,4))
        self.assertEqual(self.m.byte_range('bytes=-3',10),(7,9))
        self.assertEqual(self.m.byte_range('bytes=3-',10),(3,9))
        for v in ['bytes=20-','bytes=4-2','bytes=0-1,4-5','garbage']:
            with self.assertRaises(ValueError):self.m.byte_range(v,10)
    def test_no_cloud_route_and_security_headers(self):
        status,_,headers=self.request('/')
        self.assertEqual(status,200)
        self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertEqual(self.post('/api/cloud',{})[0],404)

if __name__=='__main__':unittest.main()
