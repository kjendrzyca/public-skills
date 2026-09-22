"""Run with: python3 -B -m unittest discover -s tests -v (from this skill)."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load_script("verify-video")


class DecodeValidationTests(unittest.TestCase):
    def verify_with_decode(self, returncode, stderr):
        stream = {
            "r_frame_rate": "60/1",
            "avg_frame_rate": "60/1",
            "time_base": "1/60000",
            "duration_ts": 3000,
            "nb_frames": "3",
        }
        responses = [
            subprocess.CompletedProcess([], 0, json.dumps({"streams": [stream]}), ""),
            subprocess.CompletedProcess(
                [], 0, json.dumps({"frames": [{"pts": n} for n in (0, 1000, 2000)]}), ""
            ),
            subprocess.CompletedProcess([], returncode, "", stderr),
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.touch()
            output = io.StringIO()
            with (
                patch.object(sys, "argv", ["verify-video.py", "--input", str(source), "--json"]),
                patch.object(verify.shutil, "which", return_value="tool"),
                patch.object(verify, "run", side_effect=responses) as run,
                contextlib.redirect_stdout(output),
            ):
                status = verify.main()
            result = json.loads(output.getvalue())
            decode = next(check for check in result["checks"] if check["name"] == "full-decode")
            # Timing is deliberately valid, so it cannot hide a decode-check defect.
            self.assertTrue(all(c["passed"] for c in result["checks"] if c["name"] != "full-decode"))
            return status, result, decode, run.call_args_list[-1].args[0]

    def test_clean_decode_passes(self):
        status, result, decode, _ = self.verify_with_decode(0, "")
        self.assertEqual(status, 0)
        self.assertTrue(result["valid"])
        self.assertTrue(decode["passed"])

    def test_decoder_errors_fail_even_with_zero_exit(self):
        message = "Invalid data found when processing input"
        status, result, decode, _ = self.verify_with_decode(0, message)
        self.assertEqual(status, 1)
        self.assertFalse(result["valid"])
        self.assertFalse(decode["passed"])
        self.assertIn(message, decode["detail"])

    def test_nonzero_decoder_exit_fails(self):
        status, result, decode, _ = self.verify_with_decode(1, "decoder failed")
        self.assertEqual(status, 1)
        self.assertFalse(result["valid"])
        self.assertFalse(decode["passed"])

    def test_decoder_stops_on_errors(self):
        _, _, _, command = self.verify_with_decode(0, "")
        self.assertIn("-xerror", command)
        self.assertLess(command.index("-xerror"), command.index("-i"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires ffmpeg and ffprobe")
class CropValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.source = cls.directory / "source.mp4"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "testsrc2=size=160x120:rate=60", "-t", "0.2",
                "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p",
                "-video_track_timescale", "60000", str(cls.source),
            ],
            check=True, capture_output=True, timeout=30,
        )

    def normalize(self, output, crop, *flags):
        return subprocess.run(
            [
                sys.executable, str(SCRIPTS / "normalize-video.py"),
                "--input", str(self.source), "--output", str(output),
                "--crop", crop, *flags,
            ],
            text=True, capture_output=True, timeout=30,
        )

    def test_crop_outside_either_edge_is_rejected_before_output(self):
        for crop in ("80:60:100:0", "80:60:0:70", "162:120:0:0"):
            with self.subTest(crop=crop):
                output = self.directory / f"outside-{crop.replace(':', '-')}.mp4"
                result = self.normalize(output, crop)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("bounds", result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(list(self.directory.glob(f".{output.stem}.normalizing-*")), [])

    def test_invalid_crop_does_not_replace_existing_output(self):
        output = self.directory / "existing.mp4"
        output.write_bytes(b"keep this file")
        result = self.normalize(output, "80:60:100:70", "--overwrite")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(output.read_bytes(), b"keep this file")

    def test_crop_touching_edges_remains_valid(self):
        output = self.directory / "valid.mp4"
        result = self.normalize(output, "80:60:80:60")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        verified = subprocess.run(
            [
                sys.executable, str(SCRIPTS / "verify-video.py"),
                "--input", str(output), "--expected-width", "80",
                "--expected-height", "60", "--json",
            ],
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertTrue(json.loads(verified.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
