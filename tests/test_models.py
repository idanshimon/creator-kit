import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ModelsTests(unittest.TestCase):
    def mod(self):
        path = ROOT / 'creator_tools' / 'models.py'
        self.assertTrue(path.exists(), 'Creator model integration is missing')
        spec = importlib.util.spec_from_file_location('models', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_capabilities_are_not_all_video_generation(self):
        m = self.mod()
        for name, kind in [('gpt-4o-mini','chat'),('gpt-5','chat'),('gpt-image-2','image'),('whisper','transcription'),('gpt-4o-transcribe-diarize','transcription'),('text-embedding-3-small','embedding'),('gpt-realtime-2.1','realtime'),('unknown-new-model','unknown')]:
            self.assertEqual(m.capability(name),kind)

    def test_endpoint_rejects_non_azure_and_credential_urls(self):
        m = self.mod()
        for endpoint in ['http://x.openai.azure.com','https://x.openai.azure.com.evil.test','https://user:password@x.openai.azure.com','https://x.openai.azure.com/path','https://x.openai.azure.com?secret=1','https://127.0.0.1']:
            with self.assertRaises(ValueError): m.validate_endpoint(endpoint)
        self.assertEqual(m.validate_endpoint('https://example.openai.azure.com/'),'https://example.openai.azure.com')

    def test_inventory_selection_is_exact_and_not_claimed_verified(self):
        m = self.mod()
        inventory={'subscription':'test','accounts':[{'account':'dev','resource_group':'rg','endpoint':'https://dev.openai.azure.com/','deployments':[{'name':'gpt-test','model':{'name':'gpt-4o-mini'},'state':'Succeeded'}]}]}
        rows=m.model_rows(inventory)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['id'],'dev/gpt-test')
        self.assertFalse(rows[0]['inference_verified'])
        self.assertEqual(m.select_model(inventory,'dev/gpt-test','chat')['deployment'],'gpt-test')
        with self.assertRaises(ValueError): m.select_model(inventory,'dev/gpt-test','image')
        with self.assertRaises(ValueError): m.select_model(inventory,'missing','chat')

    def test_response_json_fences_and_prose(self):
        m = self.mod()
        self.assertEqual(m.parse_plan_json('```json\n{"version":1}\n```'), {'version':1})
        for bad in ['Here is a plan: {"version":1}', '[]','{"x":NaN}']:
            with self.assertRaises(ValueError): m.parse_plan_json(bad)

    def test_plan_can_only_reference_explicitly_supplied_sources(self):
        m = self.mod()
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'clip.mp4';p.touch()
            source={'path':str(p),'duration':4,'width':320,'height':180,'has_audio':False}
            response={'version':1,'clips':[{'path':str(p),'start':0,'end':2}],'width':320,'height':180,'fit':'contain','mute':False,'volume':1}
            with patch.object(m,'chat',return_value=json.dumps(response)) as call:
                got=m.make_plan({},'test','trim',[source])
                self.assertEqual(got,response)
                self.assertIn('metadata',str(call.call_args).lower())
            response['clips'][0]['path']='/etc/passwd'
            with patch.object(m,'chat',return_value=json.dumps(response)):
                with self.assertRaises(ValueError): m.make_plan({},'test','trim',[source])

    def test_chat_uses_encrypted_endpoint_and_token_in_header(self):
        m = self.mod()
        inventory={'subscription':'test','accounts':[{'account':'dev','resource_group':'rg','endpoint':'https://dev.openai.azure.com','deployments':[{'name':'small','model':{'name':'gpt-4o-mini'},'state':'Succeeded'}]}]}
        with patch.object(m,'access_token',return_value='unit-test-token'),patch.object(m,'request_json',return_value={'choices':[{'message':{'content':'ok'}}]}) as request:
            self.assertEqual(m.chat(inventory,'dev/small',[{'role':'user','content':'hello'}]),'ok')
            url,payload,headers=request.call_args.args
            self.assertNotIn('unit-test-token',url)
            self.assertEqual(headers['Authorization'],'Bearer unit-test-token')
            self.assertEqual(payload['messages'][0]['content'],'hello')

if __name__ == '__main__': unittest.main()
