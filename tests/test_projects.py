import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ProjectTests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'creator_tools'/'projects.py'
        self.assertTrue(p.exists(),'Persistent project store missing')
        spec=importlib.util.spec_from_file_location('projects',p)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=self.m.Store(self.root)
    def tearDown(self):
        if hasattr(self,'temp'):self.temp.cleanup()
    def test_create_persists_across_instances(self):
        p=self.store.create('My edit')
        self.assertEqual(p['plan']['clips'],[])
        self.assertEqual(self.m.Store(self.root).get(p['id'])['name'],'My edit')
    def test_revisions_undo_redo_and_branch_preserve_history(self):
        p=self.store.create('Original')
        q=self.store.save(p['id'],p['plan'],p['revision'],name='Renamed',label='Rename')
        old=self.store.undo(p['id'],q['revision'])
        self.assertEqual(old['name'],'Original')
        self.assertTrue(old['can_redo'])
        newer=self.store.redo(p['id'],old['revision'])
        self.assertEqual(newer['name'],'Renamed')
        old=self.store.undo(p['id'],newer['revision'])
        branch=self.store.save(p['id'],old['plan'],old['revision'],name='New branch')
        self.assertFalse(branch['can_redo'])
        self.assertGreater(branch['revision'],newer['revision'])
        self.assertEqual(len(branch['history']),3)
    def test_stale_revision_rejected(self):
        p=self.store.create('Edit')
        self.store.save(p['id'],p['plan'],p['revision'],name='New')
        with self.assertRaises(self.m.Conflict):self.store.save(p['id'],p['plan'],p['revision'],name='Stale')
    def test_no_arbitrary_paths_or_unknown_keys(self):
        p=self.store.create('Edit');plan=p['plan']
        plan['clips']=[{'path':'/etc/passwd','start':0,'end':1}]
        with self.assertRaises(ValueError):self.store.save(p['id'],plan,p['revision'])
        plan=p['plan'];plan['clips']=[];plan['shell']='whoami'
        with self.assertRaises(ValueError):self.store.save(p['id'],plan,p['revision'])
    def test_import_real_video_and_save(self):
        src=self.root/'fixture.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=160x120:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(src)],check=True)
        a=self.store.import_asset('sample.mp4',src.read_bytes())
        self.assertEqual(a['width'],160)
        self.assertEqual(self.store.asset(a['id'])['path'],a['path'])
        p=self.store.create('Edit');plan=p['plan'];plan['clips']=[{'path':a['path'],'start':0,'end':0.8}]
        q=self.store.save(p['id'],plan,p['revision'])
        self.assertEqual(q['plan']['clips'][0]['path'],a['path'])
    def test_import_invalid_removes_temporary_file(self):
        with self.assertRaises(ValueError):self.store.import_asset('fake.mp4',b'not video')
        self.assertEqual(self.store.assets(),[])
        self.assertEqual(list((self.root/'media').iterdir()),[])
    def test_invalid_project_ids_and_names(self):
        with self.assertRaises(ValueError):self.store.get('../etc/passwd')
        with self.assertRaises(ValueError):self.store.create(' ')

if __name__=='__main__':unittest.main()
