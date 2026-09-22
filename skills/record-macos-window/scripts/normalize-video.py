#!/usr/bin/env python3
"""Normalize a ScreenCaptureKit recording to an exact CFR delivery file."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize a video to exact constant 60 fps H.264 and verify its timeline."
    )
    parser.add_argument("--input", required=True, help="Raw source video.")
    parser.add_argument("--output", required=True, help="Normalized MP4 destination.")
    parser.add_argument(
        "--trim-start",
        type=float,
        default=0.0,
        help="First source timestamp to keep, in seconds. Default: 0.",
    )
    parser.add_argument(
        "--trim-end",
        type=float,
        help="Last source timestamp to keep, in seconds.",
    )
    parser.add_argument(
        "--crop",
        help="Strict ffmpeg pixel crop WIDTH:HEIGHT:X:Y, using non-negative integers.",
    )
    parser.add_argument(
        "--scale",
        help="Output WIDTH:HEIGHT. Each value must be positive, -1, or -2.",
    )
    parser.add_argument("--crf", type=int, default=18, help="H.264 CRF quality. Default: 18.")
    parser.add_argument(
        "--preset",
        choices=("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"),
        default="slow",
        help="libx264 preset. Default: slow.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output after the new file passes verification.")
    return parser.parse_args()


def error(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 2


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_crop(value: str) -> str:
    match = re.fullmatch(r"(\d+):(\d+):(\d+):(\d+)", value)
    if not match or int(match.group(1)) <= 0 or int(match.group(2)) <= 0:
        raise ValueError("--crop must be WIDTH:HEIGHT:X:Y with positive size and non-negative offsets.")
    return value


def parse_scale(value: str) -> str:
    match = re.fullmatch(r"(-?\d+):(-?\d+)", value)
    if not match:
        raise ValueError("--scale must be WIDTH:HEIGHT.")
    dimensions = [int(match.group(1)), int(match.group(2))]
    if any(dimension == 0 or dimension < -2 for dimension in dimensions):
        raise ValueError("--scale values must be positive, -1, or -2.")
    if all(dimension < 0 for dimension in dimensions):
        raise ValueError("--scale requires at least one positive dimension.")
    return value


def probe_duration(input_path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return float(result.stdout.strip())


def probe_dimensions(input_path: Path) -> tuple[int, int]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(input_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exception:
        raise RuntimeError(f"could not read video dimensions: {exception}") from exception


def validate_crop_bounds(crop: str, video_width: int, video_height: int) -> None:
    width, height, x_offset, y_offset = (int(part) for part in crop.split(":"))
    if x_offset + width > video_width or y_offset + height > video_height:
        raise ValueError(
            f"--crop {crop} exceeds the {video_width}:{video_height} video bounds."
        )


def absolute_without_resolving(path: str) -> Path:
    return Path(os.path.abspath(Path(path).expanduser()))


def inspect_destination(path: Path) -> tuple[str, tuple[int, int] | None]:
    try:
        information = os.lstat(path)
    except FileNotFoundError:
        return "absent", None
    if stat.S_ISLNK(information.st_mode):
        return "symlink", None
    if stat.S_ISREG(information.st_mode):
        return "regular", (information.st_dev, information.st_ino)
    return "non-regular", None


def destination_still_installable(
    initial: tuple[str, tuple[int, int] | None],
    current: tuple[str, tuple[int, int] | None],
) -> bool:
    initial_kind, initial_identity = initial
    current_kind, current_identity = current
    if current_kind == "symlink":
        return False
    if initial_kind == "absent":
        return current_kind == "absent"
    return current_kind == "regular" and current_identity == initial_identity


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = absolute_without_resolving(args.output)

    if not input_path.is_file():
        return error(f"input file not found: {input_path}")
    if output_path.suffix.lower() != ".mp4":
        return error("--output must use the .mp4 extension.")
    if args.trim_start < 0:
        return error("--trim-start cannot be negative.")
    if args.trim_end is not None and args.trim_end <= args.trim_start:
        return error("--trim-end must be greater than --trim-start.")
    if not 0 <= args.crf <= 51:
        return error("--crf must be between 0 and 51.")
    for command in ("ffmpeg", "ffprobe"):
        if shutil.which(command) is None:
            return error(f"{command} was not found on PATH.")

    try:
        crop = parse_crop(args.crop) if args.crop else None
        scale = parse_scale(args.scale) if args.scale else None
        source_duration = probe_duration(input_path)
        if crop:
            video_width, video_height = probe_dimensions(input_path)
            validate_crop_bounds(crop, video_width, video_height)
    except (ValueError, RuntimeError) as exception:
        return error(str(exception))

    if args.trim_start >= source_duration:
        return error(f"--trim-start is outside the {source_duration:.3f}s source duration.")
    if args.trim_end is not None and args.trim_end > source_duration + 0.05:
        return error(f"--trim-end exceeds the {source_duration:.3f}s source duration.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    initial_destination = inspect_destination(output_path)
    if initial_destination[0] == "symlink":
        return error(f"output target is a symbolic link: {output_path}")
    if initial_destination[0] == "non-regular":
        return error(f"output target is not a regular file: {output_path}")
    if initial_destination[0] == "regular" and not args.overwrite:
        return error(f"output already exists: {output_path}. Pass --overwrite only when replacement is intended.")
    if initial_destination[0] == "regular" and os.path.samefile(input_path, output_path):
        return error("--input and --output must be different files.")
    if initial_destination[0] == "absent" and input_path == output_path:
        return error("--input and --output must be different files.")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}.normalizing-",
        suffix=".mp4",
        dir=output_path.parent,
    )
    os.close(descriptor)
    temp_path = Path(temporary_name)
    filters = []
    if crop:
        filters.append(f"crop={crop}")
    if scale:
        filters.append(f"scale={scale}:flags=lanczos")
    filters.append("fps=fps=60:round=near")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-i",
        str(input_path),
        "-ss",
        f"{args.trim_start:.6f}",
    ]
    if args.trim_end is not None:
        command.extend(["-t", f"{args.trim_end - args.trim_start:.6f}"])
    command.extend(
        [
            "-map",
            "0:v:0",
            "-vf",
            ",".join(filters),
            "-c:v",
            "libx264",
            "-preset",
            args.preset,
            "-crf",
            str(args.crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            "60",
            "-fps_mode",
            "cfr",
            "-video_track_timescale",
            "60000",
            "-movflags",
            "+faststart",
        ]
    )
    command.append("-an")
    command.append(str(temp_path))

    installed = False
    try:
        print(f"[info] normalizing: {input_path}", file=sys.stderr)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return error(f"ffmpeg failed with exit code {result.returncode}.")

        verifier = Path(__file__).with_name("verify-video.py")
        verification = run(
            [
                sys.executable,
                str(verifier),
                "--input",
                str(temp_path),
                "--expected-fps",
                "60",
                "--json",
            ]
        )
        if verification.returncode != 0:
            try:
                detail = json.dumps(json.loads(verification.stdout), indent=2)
            except json.JSONDecodeError:
                detail = verification.stdout.strip() or verification.stderr.strip()
            return error(f"normalized file failed exact-60-fps verification:\n{detail}")

        current_destination = inspect_destination(output_path)
        if current_destination[0] == "non-regular":
            return error(f"output target became a non-regular file: {output_path}")
        if not destination_still_installable(initial_destination, current_destination):
            return error(f"output target changed while normalization was running: {output_path}")
        os.replace(temp_path, output_path)
        installed = True

        verification_data = json.loads(verification.stdout)
        video = verification_data["video"]
        print(f"[ok] normalized exact 60 fps: {output_path}")
        print(
            f"[ok] {video.get('width')}x{video.get('height')}, "
            f"{verification_data['timing']['frames_checked']} frames, "
            f"{video.get('duration')}s"
        )
        return 0
    finally:
        if not installed:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
