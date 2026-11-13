import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

class CLITests(unittest.TestCase):
    def cli(self,*args):
        self.assertTrue((ROOT/'creator.py').exists(),'Creator CLI missing')
        return subprocess.run([sys.executable,str(ROOT/'creator.py'),*args],capture_output=True,text=True,cwd=ROOT)
    def test_help_exposes_real_commands(self):
        p=self.cli('--help')
        self.assertEqual(p.returncode,0,p.stderr)
        for name in ['discover','models','chat','plan','edit','image','transcribe','probe']:
            self.assertIn(name,p.stdout)
    def test_cloud_use_requires_explicit_flag_before_loading_inventory(self):
        p=self.cli('chat','--model','example/test','--prompt','hello')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('--allow-cloud',p.stderr)
    def test_models_loads_inventory_not_hardcoded_examples(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'inventory.json'
            path.write_text(json.dumps({'subscription':'test','accounts':[{'account':'dev','resource_group':'rg','endpoint':'https://dev.openai.azure.com','deployments':[{'name':'x','model':{'name':'gpt-4o-mini'},'state':'Succeeded'}]}]}))
            p=self.cli('--inventory',str(path),'models')
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)[0]['id'],'dev/x')
    def test_studio_help_and_export_profiles(self):
        p=self.cli('studio','--help')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('--port',p.stdout)
        self.assertIn('--workspace',p.stdout)
        p=self.cli('edit','--help')
        self.assertIn('--profile',p.stdout)
        self.assertIn('draft',p.stdout)

    def test_missing_plan_fails_cleanly(self):
        p=self.cli('edit','--plan','/not/a/real/plan.json','--output','/tmp/never-render.mp4')
        self.assertNotEqual(p.returncode,0)
        self.assertNotIn('Traceback',p.stderr)

if __name__=='__main__':unittest.main()
