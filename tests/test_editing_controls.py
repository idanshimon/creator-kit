"""Real (ffmpeg-backed) tests for the extended editing controls:

per-clip speed / volume / mute, global fade_in / fade_out, and the
render(..., profile=) draft/final profiles. Reuses the synthetic fixtures
from tests.test_editing. No network, no vendored code.
"""
import json
import math
import os
import shutil
import subprocess
import threading
import time
import unittest

from creator_tools import editing
from tests import test_editing as fixture

FFMPEG = fixture.FFMPEG
FFPROBE = fixture.FFPROBE
HAVE_FF = fixture.HAVE_FF


def _has_filter(name):
    if not FFMPEG:
        return False
    out = subprocess.run([FFMPEG, "-hide_banner", "-filters"], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL).stdout.decode(errors="replace")
    return any(line.split()[1:2] == [name] for line in out.splitlines() if line.strip())


HAVE_LIBASS = _has_filter("subtitles")


def _duration(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    return float(json.loads(out.decode())["format"]["duration"])


def _dims(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", path],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    s = json.loads(out.decode())["streams"][0]
    return int(s["width"]), int(s["height"])


def _rms(path, ss=None, to=None):
    """Mean volume in dB via volumedetect; very low for silence."""
    args = [FFMPEG, "-v", "info"]
    if ss is not None:
        args += ["-ss", str(ss)]
    if to is not None:
        args += ["-t", str(to)]
    args += ["-i", path, "-map", "0:a", "-af", "volumedetect",
             "-f", "null", "-"]
    err = subprocess.run(args, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE).stderr.decode()
    for line in err.splitlines():
        if "mean_volume:" in line:
            tok = line.split("mean_volume:")[-1].replace("dB", "").strip()
            try:
                return float(tok)
            except ValueError:
                return -120.0
    return -120.0


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe required")
class ControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.EditingTest.setUpClass()
        cls.a = fixture.EditingTest.a  # red 320x240 2s WITH audio
        cls.b = fixture.EditingTest.b  # blue 640x480 2s SILENT
        cls.tmp = fixture.EditingTest.tmp

    @classmethod
    def tearDownClass(cls):
        fixture.EditingTest.tearDownClass()

    def _plan(self, **over):
        plan = {"version": 1, "width": 320, "height": 240,
                "clips": [{"path": self.a, "start": 0.0, "end": 2.0}]}
        plan.update(over)
        return plan

    def _out(self, name):
        return os.path.join(self.tmp, name)

    # ---------- validation ----------
    def test_defaults_backward_compatible(self):
        n = editing.validate_plan(self._plan())
        self.assertEqual(n["fade_in"], 0.0)
        self.assertEqual(n["fade_out"], 0.0)
        c = n["clips"][0]
        self.assertEqual(c["speed"], 1.0)
        self.assertEqual(c["volume"], 1.0)
        self.assertFalse(c["mute"])
        # effective duration equals raw when speed 1
        self.assertAlmostEqual(n["total_duration"], 2.0, delta=1e-6)

    def test_reject_speed_range(self):
        for bad in (0.24, 4.01, 0):
            with self.assertRaises(editing.EditPlanError):
                editing.validate_plan(self._plan(
                    clips=[{"path": self.a, "start": 0, "end": 1, "speed": bad}]))

    def test_reject_clip_volume_range(self):
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(
                clips=[{"path": self.a, "start": 0, "end": 1, "volume": 2.5}]))

    def test_reject_clip_mute_type(self):
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(
                clips=[{"path": self.a, "start": 0, "end": 1, "mute": "yes"}]))

    def test_reject_unknown_clip_key_still(self):
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(
                clips=[{"path": self.a, "start": 0, "end": 1, "zoom": 2}]))

    def test_reject_unknown_top_key_still(self):
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(bogus=1))

    def test_effective_total_duration_uses_speed(self):
        n = editing.validate_plan(self._plan(
            clips=[{"path": self.a, "start": 0, "end": 2, "speed": 4}]))
        self.assertAlmostEqual(n["total_duration"], 0.5, delta=1e-6)

    def test_effective_total_duration_cap(self):
        # slow a clip enough to exceed 600s effective -> rejected
        clips = [{"path": self.a, "start": 0, "end": 2, "speed": 0.25}
                 for _ in range(100)]  # 100 * (2/0.25)=800 > 600
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(clips=clips))

    def test_reject_negative_fade(self):
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(fade_in=-0.1))

    def test_reject_fade_exceeds_half(self):
        # total effective 2.0 -> fade must be <= 1.0
        with self.assertRaises(editing.EditPlanError):
            editing.validate_plan(self._plan(fade_in=1.5))

    def test_reject_bad_profile(self):
        with self.assertRaises(editing.EditPlanError):
            editing.render(self._plan(), self._out("np.mp4"), profile="turbo")

    # ---------- render: speed changes real duration ----------
    def test_speed_shortens_duration(self):
        out = self._out("speed2.mp4")
        editing.render(self._plan(
            clips=[{"path": self.a, "start": 0, "end": 2, "speed": 2.0}]), out)
        self.assertAlmostEqual(_duration(out), 1.0, delta=0.25)

    def test_speed_slow_lengthens_duration(self):
        out = self._out("speed_half.mp4")
        editing.render(self._plan(
            clips=[{"path": self.a, "start": 0, "end": 1, "speed": 0.5}]), out)
        self.assertAlmostEqual(_duration(out), 2.0, delta=0.3)

    def test_silence_duration_follows_speed(self):
        # silent source, sped up: output duration must reflect effective time
        out = self._out("silent_speed.mp4")
        editing.render({"version": 1, "width": 320, "height": 240,
                        "clips": [{"path": self.b, "start": 0, "end": 2,
                                   "speed": 4.0}]}, out)
        self.assertAlmostEqual(_duration(out), 0.5, delta=0.25)

    # ---------- render: volume / mute via RMS ----------
    def test_clip_mute_produces_silence(self):
        out = self._out("clipmute.mp4")
        editing.render(self._plan(
            clips=[{"path": self.a, "start": 0, "end": 2, "mute": True}]), out)
        self.assertLess(_rms(out), -50.0)

    def test_clip_volume_multiplies_global(self):
        loud = self._out("loud.mp4")
        quiet = self._out("quiet.mp4")
        editing.render(self._plan(volume=1.0,
            clips=[{"path": self.a, "start": 0, "end": 2, "volume": 1.0}]), loud)
        editing.render(self._plan(volume=0.5,
            clips=[{"path": self.a, "start": 0, "end": 2, "volume": 0.5}]), quiet)
        # 0.5 * 0.5 = 0.25 gain -> ~ -12 dB quieter
        self.assertLess(_rms(quiet), _rms(loud) - 6.0)

    # ---------- render: fades ----------
    def test_fades_attenuate_edges(self):
        out = self._out("faded.mp4")
        editing.render(self._plan(fade_in=0.5, fade_out=0.5,
            clips=[{"path": self.a, "start": 0, "end": 2}]), out)
        # audio near the very start is attenuated vs the middle
        edge = _rms(out, ss=0.0, to=0.15)
        mid = _rms(out, ss=0.9, to=0.2)
        self.assertLess(edge, mid - 6.0)
        # video first frame is darker (fading up from black) than middle
        r0, g0, b0 = fixture._avg_rgb(out, 0.02)
        rm, gm, bm = fixture._avg_rgb(out, 1.0)
        self.assertLess(r0, rm)

    # ---------- profiles ----------
    def test_draft_downscales_max_dim_640(self):
        out = self._out("draft.mp4")
        res = editing.render({"version": 1, "width": 1280, "height": 720,
                              "clips": [{"path": self.a, "start": 0,
                                         "end": 1}]}, out, profile="draft")
        w, h = _dims(out)
        self.assertEqual(max(w, h), 640)
        self.assertEqual(w % 2, 0)
        self.assertEqual(h % 2, 0)
        # aspect preserved (16:9 -> 640x360)
        self.assertEqual((w, h), (640, 360))
        self.assertEqual(res["profile"], "draft")

    def test_final_keeps_full_dims(self):
        out = self._out("final.mp4")
        res = editing.render({"version": 1, "width": 1280, "height": 720,
                              "clips": [{"path": self.a, "start": 0,
                                         "end": 1}]}, out, profile="final")
        self.assertEqual(_dims(out), (1280, 720))
        self.assertEqual(res["profile"], "final")

    def test_draft_no_upscale(self):
        out = self._out("draft_small.mp4")
        editing.render(self._plan(width=320, height=240,
            clips=[{"path": self.a, "start": 0, "end": 1}]),
            out, profile="draft")
        self.assertEqual(_dims(out), (320, 240))

    # ---------- provenance ----------
    def test_provenance_has_effective_and_input_hashes(self):
        out = self._out("prov.mp4")
        editing.render(self._plan(fade_in=0.25, fade_out=0.25,
            clips=[{"path": self.a, "start": 0, "end": 2, "speed": 2.0,
                    "volume": 0.5}]), out)
        with open(out + ".provenance.json") as f:
            prov = json.loads(f.read())
        self.assertIn("effective", prov)
        eff = prov["effective"]
        self.assertAlmostEqual(eff["total_duration"], 1.0, delta=1e-6)
        self.assertEqual(eff["fade_in"], 0.25)
        c0 = eff["clips"][0]
        self.assertEqual(c0["speed"], 2.0)
        self.assertAlmostEqual(c0["effective_volume"], 0.5, delta=1e-6)
        self.assertAlmostEqual(c0["effective_duration"], 1.0, delta=1e-6)
        # input hashes captured (before render) + change-detection flag present
        self.assertTrue(prov["inputs"][0]["sha256"])
        self.assertIn("inputs_changed_during_render", prov)
        self.assertFalse(prov["inputs_changed_during_render"])
        self.assertEqual(prov["profile"], "final")

    # ---------- subtitle retiming + burn-in ----------
    def test_retime_subtitles_shifts_and_scales_across_cuts(self):
        srt = (
            "1\n00:00:00,100 --> 00:00:00,900\nFIRST\n\n"
            "2\n00:00:01,100 --> 00:00:01,900\nSECOND\n"
        )
        # Keep only 1.0..2.0 at 2x speed -> effective window 0.0..0.5s
        clips = [{"path": self.a, "start": 1.0, "end": 2.0, "speed": 2.0}]
        retimed = editing.retime_subtitles(srt, clips, fmt="srt")
        cues = editing.parse_subtitle_cues(retimed)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]["text"], "SECOND")
        self.assertAlmostEqual(cues[0]["start"], 0.05, delta=0.01)
        self.assertAlmostEqual(cues[0]["end"], 0.45, delta=0.01)

    @unittest.skipUnless(HAVE_LIBASS, "ffmpeg built without libass (no 'subtitles' filter)")
    def test_render_with_retimed_and_burned_subtitles(self):
        sub_path = self._out("source_subs.srt")
        with open(sub_path, "w") as f:
            f.write(
                "1\n00:00:00,100 --> 00:00:00,800\nDROPPED\n\n"
                "2\n00:00:01,100 --> 00:00:01,900\nKEPT LINE\n"
            )
        out = self._out("retimed_burned.mp4")
        plan = self._plan(
            clips=[{"path": self.b, "start": 1.0, "end": 2.0}],
            subtitles=sub_path,
            retime_subtitles=True,
            burn_subtitles=True,
        )
        editing.render(plan, out)
        # Embedded mov_text stream should carry ONLY the retimed KEPT LINE
        assert FFMPEG is not None
        extracted = subprocess.check_output(
            [FFMPEG, "-v", "error", "-i", out, "-map", "0:s:0", "-f", "srt", "-"]
        ).decode()
        self.assertIn("KEPT LINE", extracted)
        self.assertNotIn("DROPPED", extracted)
        cues = editing.parse_subtitle_cues(extracted)
        self.assertAlmostEqual(cues[0]["start"], 0.1, delta=0.05)

    # ---------- BGM bed + sidechain ducking ----------
    def test_bgm_mix_and_sidechain_ducking(self):
        assert FFMPEG is not None
        bgm_path = self._out("bgm_bed.wav")
        subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=3", bgm_path],
            check=True
        )
        # Render silent video clip (self.b) with BGM -> output is no longer silent (-120 dB)
        out_silent_plus_bgm = self._out("bgm_on_silent.mp4")
        editing.render(
            {"version": 1, "width": 320, "height": 240,
             "clips": [{"path": self.b, "start": 0, "end": 2}],
             "bgm": bgm_path, "bgm_volume": 0.8, "bgm_duck": True},
            out_silent_plus_bgm
        )
        rms_un_ducked = _rms(out_silent_plus_bgm)
        self.assertGreater(rms_un_ducked, -35.0)
        # Render voiced clip (self.a, muted in main mix? no, compare BGM ducked vs unducked when voice plays)
        out_ducked = self._out("bgm_ducked.mp4")
        out_unducked = self._out("bgm_unducked.mp4")
        editing.render(
            {"version": 1, "width": 320, "height": 240,
             "clips": [{"path": self.a, "start": 0, "end": 2, "volume": 0.5}],
             "bgm": bgm_path, "bgm_volume": 1.0, "bgm_duck": True},
            out_ducked
        )
        editing.render(
            {"version": 1, "width": 320, "height": 240,
             "clips": [{"path": self.a, "start": 0, "end": 2, "volume": 0.5}],
             "bgm": bgm_path, "bgm_volume": 1.0, "bgm_duck": False},
            out_unducked
        )
        self.assertLess(_rms(out_ducked), _rms(out_unducked))

    def test_analyze_clip_detects_silence_and_srt(self):
        srt_path = self._out("probe.srt")
        with open(srt_path, "w") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\nHELLO\n")
        info = editing.analyze_clip(self.a, srt_path=srt_path)
        self.assertIn("silences", info)
        self.assertIn("scene_cuts", info)
        self.assertEqual(len(info["transcript"]), 1)
        self.assertEqual(info["transcript"][0]["text"], "HELLO")


if __name__ == "__main__":
    unittest.main()
