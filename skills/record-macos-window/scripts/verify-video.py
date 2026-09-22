#!/usr/bin/env python3
"""Verify that a video has an exact constant-frame-rate presentation timeline."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify exact constant frame timing and optional video dimensions."
    )
    parser.add_argument("--input", required=True, help="Video file to verify.")
    parser.add_argument(
        "--expected-fps",
        type=int,
        default=60,
        help="Required constant frame rate. Default: 60.",
    )
    parser.add_argument("--expected-width", type=int, help="Required pixel width.")
    parser.add_argument("--expected-height", type=int, help="Required pixel height.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write the complete result as JSON instead of a human summary.",
    )
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fail(message: str, *, json_output: bool) -> int:
    if json_output:
        print(json.dumps({"valid": False, "error": message}, indent=2))
    else:
        print(f"Error: {message}", file=sys.stderr)
    return 2


def fraction(value: str) -> Fraction:
    if not value or value == "0/0":
        return Fraction(0, 1)
    return Fraction(value)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()

    if args.expected_fps <= 0:
        return fail("--expected-fps must be positive.", json_output=args.json)
    if not input_path.is_file():
        return fail(f"input file not found: {input_path}", json_output=args.json)
    for command in ("ffmpeg", "ffprobe"):
        if shutil.which(command) is None:
            return fail(f"{command} was not found on PATH.", json_output=args.json)

    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,time_base,duration_ts,duration,nb_frames",
            "-of",
            "json",
            str(input_path),
        ]
    )
    if probe.returncode != 0:
        return fail(
            f"ffprobe could not inspect the video: {probe.stderr.strip()}",
            json_output=args.json,
        )

    try:
        streams = json.loads(probe.stdout).get("streams", [])
        stream = streams[0]
    except (json.JSONDecodeError, IndexError, TypeError) as error:
        return fail(f"no readable video stream: {error}", json_output=args.json)

    frames_probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=pts",
            "-of",
            "json",
            str(input_path),
        ]
    )
    if frames_probe.returncode != 0:
        return fail(
            f"ffprobe could not read frame timestamps: {frames_probe.stderr.strip()}",
            json_output=args.json,
        )

    try:
        raw_frames = json.loads(frames_probe.stdout).get("frames", [])
        frame_pts = [int(frame["pts"]) for frame in raw_frames if "pts" in frame]
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return fail(f"invalid frame timestamp data: {error}", json_output=args.json)

    full_decode = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-f",
            "null",
            "-",
        ]
    )

    expected_rate = Fraction(args.expected_fps, 1)
    declared_rate = fraction(str(stream.get("r_frame_rate", "0/0")))
    average_rate = fraction(str(stream.get("avg_frame_rate", "0/0")))
    time_base = fraction(str(stream.get("time_base", "0/0")))
    expected_tick_step = Fraction(1, args.expected_fps) / time_base if time_base else Fraction(0, 1)
    tick_step_is_exact = expected_tick_step.denominator == 1 and expected_tick_step > 0
    expected_ticks = int(expected_tick_step) if tick_step_is_exact else None
    intervals = [right - left for left, right in zip(frame_pts, frame_pts[1:])]
    bad_intervals = (
        [interval for interval in intervals if interval != expected_ticks]
        if expected_ticks is not None
        else intervals
    )

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "declared-frame-rate",
        declared_rate == expected_rate,
        f"expected {args.expected_fps}/1, found {stream.get('r_frame_rate', 'missing')}",
    )
    add_check(
        checks,
        "average-frame-rate",
        average_rate == expected_rate,
        f"expected {args.expected_fps}/1, found {stream.get('avg_frame_rate', 'missing')}",
    )
    add_check(
        checks,
        "exact-time-base",
        tick_step_is_exact,
        (
            f"one frame equals {expected_ticks} ticks at time base {stream.get('time_base')}"
            if tick_step_is_exact
            else f"time base {stream.get('time_base', 'missing')} cannot represent 1/{args.expected_fps} exactly"
        ),
    )
    add_check(
        checks,
        "frame-timestamps-present",
        bool(frame_pts),
        f"read {len(frame_pts)} presentation timestamps",
    )
    add_check(
        checks,
        "starts-at-zero",
        bool(frame_pts) and frame_pts[0] == 0,
        f"first presentation timestamp: {frame_pts[0] if frame_pts else 'missing'}",
    )
    add_check(
        checks,
        "constant-frame-intervals",
        bool(frame_pts) and not bad_intervals,
        (
            f"all {len(intervals)} intervals equal {expected_ticks} ticks"
            if not bad_intervals and expected_ticks is not None
            else f"found {len(bad_intervals)} irregular intervals; examples: {bad_intervals[:8]}"
        ),
    )

    declared_frame_count = stream.get("nb_frames")
    count_matches = declared_frame_count in (None, "N/A") or int(declared_frame_count) == len(frame_pts)
    add_check(
        checks,
        "frame-count",
        count_matches,
        f"ffprobe declares {declared_frame_count}; read {len(frame_pts)} timestamps",
    )

    duration_ts = stream.get("duration_ts")
    duration_matches = True
    expected_duration_ts = None
    if expected_ticks is not None and frame_pts and duration_ts not in (None, "N/A"):
        expected_duration_ts = len(frame_pts) * expected_ticks
        duration_matches = int(duration_ts) == expected_duration_ts
    add_check(
        checks,
        "stream-duration",
        duration_matches,
        f"duration_ts is {duration_ts}; expected {expected_duration_ts}",
    )
    decode_errors = full_decode.stderr.strip()
    decode_ok = full_decode.returncode == 0 and not decode_errors
    add_check(
        checks,
        "full-decode",
        decode_ok,
        (
            "ffmpeg decoded the complete video stream without errors"
            if decode_ok
            else f"ffmpeg decode failed (exit {full_decode.returncode}): {decode_errors[:500]}"
        ),
    )

    if args.expected_width is not None:
        add_check(
            checks,
            "width",
            stream.get("width") == args.expected_width,
            f"expected {args.expected_width}, found {stream.get('width')}",
        )
    if args.expected_height is not None:
        add_check(
            checks,
            "height",
            stream.get("height") == args.expected_height,
            f"expected {args.expected_height}, found {stream.get('height')}",
        )

    valid = all(check["passed"] for check in checks)
    result = {
        "valid": valid,
        "input": str(input_path),
        "video": stream,
        "timing": {
            "expected_fps": args.expected_fps,
            "expected_tick_step": expected_ticks,
            "frames_checked": len(frame_pts),
            "intervals_checked": len(intervals),
            "irregular_interval_count": len(bad_intervals),
            "irregular_interval_examples": bad_intervals[:8],
        },
        "checks": checks,
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if valid else "FAIL"
        print(f"{status}: {input_path}")
        for check in checks:
            marker = "ok" if check["passed"] else "fail"
            print(f"[{marker}] {check['name']}: {check['detail']}")

    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
