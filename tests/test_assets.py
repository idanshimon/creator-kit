import importlib.util
import base64
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]

class AssetTests(unittest.TestCase):
    def mod(self):
        p=ROOT/'creator_tools'/'assets.py'
        self.assertTrue(p.exists(),'Asset model adapter missing')
        spec=importlib.util.spec_from_file_location('assets',p)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

    def inventory(self, model='gpt-image-2'):
        return {'subscription':'test','accounts':[{'account':'dev','resource_group':'rg','endpoint':'https://dev.openai.azure.com','deployments':[{'name':'model','model':{'name':model},'state':'Succeeded'}]}]}

    def test_generation_writes_image_and_provenance_not_secrets(self):
        m=self.mod()
        with tempfile.TemporaryDirectory() as d:
            out=pathlib.Path(d)/'image.png'
            png=b'\x89PNG\r\n\x1a\n'+b'fixture'
            with patch.object(m,'access_token',return_value='secret-for-unit-test'),patch.object(m,'request_json',return_value={'data':[{'b64_json':base64.b64encode(png).decode()}]}):
                r=m.generate_image(self.inventory(),'dev/model','blue circle',out)
            self.assertEqual(out.read_bytes(),png)
            self.assertEqual(r['model'],'dev/model')
            self.assertNotIn('secret-for-unit-test',out.with_suffix('.png.provenance.json').read_text())
            with self.assertRaises(FileExistsError):m.generate_image(self.inventory(),'dev/model','blue circle',out)

    def test_image_rejects_nonimage_and_unknown_size(self):
        m=self.mod()
        with tempfile.TemporaryDirectory() as d:
            out=pathlib.Path(d)/'image.png'
            with self.assertRaises(ValueError): m.generate_image(self.inventory(),'dev/model','test',out,size='999999x999999')
            with patch.object(m,'access_token',return_value='unit'),patch.object(m,'request_json',return_value={'data':[{'b64_json':base64.b64encode(b'not png').decode()}]}):
                with self.assertRaises(ValueError):m.generate_image(self.inventory(),'dev/model','test',out)
            self.assertFalse(out.exists())

    def test_transcription_only_whisper_srt_and_no_unsupported_claim(self):
        m=self.mod()
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'audio.wav';path.write_bytes(b'RIFF'+b'0'*100)
            out=pathlib.Path(d)/'captions.srt'
            with self.assertRaises(ValueError):m.transcribe(self.inventory('gpt-4o-transcribe-diarize'),'dev/model',path,out)
            srt='1\n00:00:00,000 --> 00:00:01,000\nHello\n'
            with patch.object(m,'access_token',return_value='unit'),patch.object(m,'post_multipart',return_value=srt) as post:
                m.transcribe(self.inventory('whisper'),'dev/model',path,out)
                self.assertEqual(out.read_text(),srt)
                self.assertIn('response_format',str(post.call_args))

if __name__=='__main__':unittest.main()
