import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from creator_tools import editing
from tests import test_editing as fixture
FFMPEG = fixture.FFMPEG

class HardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.EditingTest.setUpClass()
        cls.a=fixture.EditingTest.a;cls.b=fixture.EditingTest.b;cls.tmp=fixture.EditingTest.tmp
    @classmethod
    def tearDownClass(cls): fixture.EditingTest.tearDownClass()
    def plan(self,**kwargs):
        p={'version':1,'width':320,'height':240,'clips':[{'path':self.a,'start':0,'end':1}]}
        p.update(kwargs);return p
    def test_boolean_is_not_schema_version(self):
        with self.assertRaises(editing.EditPlanError):editing.validate_plan(self.plan(version=True))
    def test_reject_audio_as_video(self):
        path=str(Path(self.tmp)/'audio.wav')
        subprocess.run([FFMPEG,'-v','error','-f','lavfi','-i','sine=d=1',path],check=True)
        with self.assertRaises(editing.EditPlanError):editing.validate_plan(self.plan(clips=[{'path':path,'start':0,'end':1}]))
    def test_probe_does_not_follow_local_playlist(self):
        playlist=Path(self.tmp)/'playlist.ffconcat'
        playlist.write_text("ffconcat version 1.0\nfile 'clip a.mp4'\n")
        with self.assertRaises(editing.EditPlanError):editing.probe(str(playlist))
    def test_output_directory_created(self):
        output=Path(self.tmp)/'fresh'/'renders'/'video.mp4'
        editing.render(self.plan(),str(output))
        self.assertTrue(output.is_file())
    def test_refuses_wrong_output_extension(self):
        with self.assertRaises(editing.EditPlanError):editing.render(self.plan(),str(Path(self.tmp)/'wrong.png'))
    def test_preserves_existing_provenance(self):
        output=Path(self.tmp)/'existing-sidecar.mp4'
        side=Path(str(output)+'.provenance.json');side.write_text('original record')
        with self.assertRaises(editing.EditPlanError):editing.render(self.plan(),str(output))
        self.assertEqual(side.read_text(),'original record')
        self.assertFalse(output.exists())
    def test_subtitles_are_actually_embedded(self):
        sub=Path(self.tmp)/"caption's file.srt"
        sub.write_text('1\n00:00:00,000 --> 00:00:00,800\nCREATOR CAPTION\n')
        out=str(Path(self.tmp)/'subtitled.mp4')
        editing.render(self.plan(subtitles=str(sub)),out)
        data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',out]))
        self.assertTrue(any(s['codec_type']=='subtitle' for s in data['streams']),'Subtitle plan accepted but ignored')
        text=subprocess.check_output([FFMPEG,'-v','error','-i',out,'-map','0:s:0','-f','srt','-']).decode()
        self.assertIn('CREATOR CAPTION',text)

if __name__=='__main__':unittest.main()
