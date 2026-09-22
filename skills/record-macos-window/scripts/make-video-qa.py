#!/usr/bin/env python3
"""Generate broad and focused visual QA sheets from a video."""

from __future__ import annotations

import argparse
import json
import math
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
        description="Generate a broad contact sheet and focused 60 fps motion strips."
    )
    parser.add_argument("--input", required=True, help="Video file to inspect.")
    parser.add_argument("--output-dir", required=True, help="Directory for QA artifacts.")
    parser.add_argument("--columns", type=int, default=4, help="Contact sheet columns. Default: 4.")
    parser.add_argument("--rows", type=int, default=4, help="Contact sheet rows. Default: 4.")
    parser.add_argument("--tile-width", type=int, default=360, help="Width of each contact tile. Default: 360.")
    parser.add_argument(
        "--focus-time",
        action="append",
        type=float,
        default=[],
        help="Center timestamp for a focused motion strip. Repeatable.",
    )
    parser.add_argument(
        "--motion-frames",
        type=int,
        default=15,
        help="Consecutive 60 fps frames in each motion strip. Default: 15.",
    )
    parser.add_argument(
        "--crop",
        help="Strict pixel crop WIDTH:HEIGHT:X:Y applied before scale to all QA images.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing regular QA artifacts after all replacements are generated.",
    )
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


def parse_crop(value: str) -> str:
    match = re.fullmatch(r"(\d+):(\d+):(\d+):(\d+)", value)
    if not match or int(match.group(1)) <= 0 or int(match.group(2)) <= 0:
        raise ValueError("--crop must be WIDTH:HEIGHT:X:Y with positive size and non-negative offsets.")
    return value


def validate_crop_bounds(crop: str, video_width: int, video_height: int) -> None:
    width, height, x_offset, y_offset = (int(part) for part in crop.split(":"))
    if x_offset + width > video_width or y_offset + height > video_height:
        raise ValueError(
            f"--crop {crop} exceeds the {video_width}:{video_height} video bounds."
        )


def absolute_without_resolving(path: str) -> Path:
    return Path(os.path.abspath(Path(path).expanduser()))


def inspect_path(path: Path) -> tuple[str, tuple[int, int] | None]:
    try:
        information = os.lstat(path)
    except FileNotFoundError:
        return "absent", None
    identity = (information.st_dev, information.st_ino)
    if stat.S_ISLNK(information.st_mode):
        return "symlink", identity
    if stat.S_ISDIR(information.st_mode):
        return "directory", identity
    if stat.S_ISREG(information.st_mode):
        return "regular", identity
    return "non-regular", identity


def prepare_output_directory(path: Path) -> tuple[int, int]:
    state = inspect_path(path)
    if state[0] == "symlink":
        raise ValueError(f"output directory is a symbolic link: {path}")
    if state[0] not in ("absent", "directory"):
        raise ValueError(f"output path is not a directory: {path}")
    if state[0] == "absent":
        path.mkdir(parents=True, exist_ok=False)
        state = inspect_path(path)
    if state[0] != "directory" or state[1] is None:
        raise ValueError(f"could not create a regular output directory: {path}")
    return state[1]


def inspect_initial_artifact(
    path: Path,
    overwrite: bool,
) -> tuple[str, tuple[int, int] | None]:
    state = inspect_path(path)
    if state[0] == "symlink":
        raise ValueError(f"artifact target is a symbolic link: {path}")
    if state[0] not in ("absent", "regular"):
        raise ValueError(f"artifact target is not a regular file: {path}")
    if state[0] == "regular" and not overwrite:
        raise FileExistsError(f"artifact already exists: {path}. Pass --overwrite to replace it.")
    return state


def install_artifact(
    temporary_path: Path,
    destination: Path,
    initial_state: tuple[str, tuple[int, int] | None],
) -> None:
    current_state = inspect_path(destination)
    if current_state[0] == "symlink":
        raise ValueError(f"artifact target became a symbolic link: {destination}")
    if current_state[0] in ("directory", "non-regular"):
        raise ValueError(f"artifact target became a non-regular file: {destination}")
    if initial_state[0] == "absent" and current_state[0] != "absent":
        raise ValueError(f"artifact target appeared while QA generation was running: {destination}")
    if initial_state[0] == "regular" and current_state != initial_state:
        raise ValueError(f"artifact target changed while QA generation was running: {destination}")
    os.replace(temporary_path, destination)


def video_filters(width: int, crop: str | None, *, fps: int | None = None) -> str:
    filters = []
    if fps is not None:
        filters.append(f"fps={fps}")
    if crop is not None:
        filters.append(f"crop={crop}")
    filters.append(f"scale={width}:-2:flags=lanczos")
    return ",".join(filters)


def extract_frame(
    input_path: Path,
    timestamp: float,
    width: int,
    crop: str | None,
    output_path: Path,
) -> None:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.6f}",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-vf",
            video_filters(width, crop),
            str(output_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not extract frame at {timestamp:.3f}s: {result.stderr.strip()}")


def tile_frames(frame_pattern: Path, columns: int, rows: int, output_path: Path) -> None:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            "1",
            "-i",
            str(frame_pattern),
            "-vf",
            f"tile={columns}x{rows}:nb_frames={columns * rows}:padding=4:margin=4:color=0x202020",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not build contact sheet: {result.stderr.strip()}")


def make_motion_strip(
    input_path: Path,
    center: float,
    duration: float,
    frames: int,
    width: int,
    crop: str | None,
    output_path: Path,
) -> tuple[float, float]:
    media_duration = duration_limit(input_path)
    start = min(max(0.0, center - duration / 2), max(0.0, media_duration - duration))
    columns = min(5, frames)
    rows = math.ceil(frames / columns)
    filters = (
        f"{video_filters(width, crop, fps=60)},"
        f"tile={columns}x{rows}:nb_frames={frames}:padding=4:margin=4:color=0x202020"
    )
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-i",
            str(input_path),
            "-t",
            f"{duration:.6f}",
            "-vf",
            filters,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not build motion strip at {center:.3f}s: {result.stderr.strip()}")
    return start, min(start + duration, media_duration)


_DURATION_CACHE: dict[Path, float] = {}


def duration_limit(input_path: Path) -> float:
    if input_path not in _DURATION_CACHE:
        _DURATION_CACHE[input_path] = probe_duration(input_path)
    return _DURATION_CACHE[input_path]


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = absolute_without_resolving(args.output_dir)

    if not input_path.is_file():
        return error(f"input file not found: {input_path}")
    if args.columns <= 0 or args.rows <= 0:
        return error("--columns and --rows must be positive.")
    if args.tile_width < 64:
        return error("--tile-width must be at least 64 pixels.")
    if not 2 <= args.motion_frames <= 60:
        return error("--motion-frames must be between 2 and 60.")
    if any(timestamp < 0 for timestamp in args.focus_time):
        return error("--focus-time values cannot be negative.")
    for command in ("ffmpeg", "ffprobe"):
        if shutil.which(command) is None:
            return error(f"{command} was not found on PATH.")

    try:
        crop = parse_crop(args.crop) if args.crop else None
        duration = probe_duration(input_path)
        if crop:
            video_width, video_height = probe_dimensions(input_path)
            validate_crop_bounds(crop, video_width, video_height)
        if duration <= 0:
            return error("video duration must be positive.")
        if any(timestamp > duration for timestamp in args.focus_time):
            return error(f"a --focus-time exceeds the {duration:.3f}s video duration.")

        output_identity = prepare_output_directory(output_dir)
        contact_path = output_dir / "contact-sheet.jpg"
        manifest_path = output_dir / "qa-manifest.json"
        motion_paths = [
            output_dir / f"motion-{index:02d}-{timestamp:.3f}s.jpg"
            for index, timestamp in enumerate(args.focus_time, start=1)
        ]
        final_paths = [contact_path, *motion_paths, manifest_path]
        initial_states = {
            path: inspect_initial_artifact(path, args.overwrite) for path in final_paths
        }

        sample_count = args.columns * args.rows
        sample_times = [duration * (index + 0.5) / sample_count for index in range(sample_count)]
        if inspect_path(output_dir) != ("directory", output_identity):
            raise ValueError(f"output directory changed before QA generation started: {output_dir}")
        with tempfile.TemporaryDirectory(
            prefix=".record-macos-window-qa-",
            dir=output_dir,
        ) as temporary_directory:
            temp_dir = Path(temporary_directory)
            frames_dir = temp_dir / "frames"
            frames_dir.mkdir()
            temporary_contact = temp_dir / contact_path.name
            temporary_manifest = temp_dir / manifest_path.name
            temporary_motions = [temp_dir / path.name for path in motion_paths]

            for index, timestamp in enumerate(sample_times):
                extract_frame(
                    input_path,
                    timestamp,
                    args.tile_width,
                    crop,
                    frames_dir / f"contact-{index:03d}.png",
                )
            tile_frames(
                frames_dir / "contact-%03d.png",
                args.columns,
                args.rows,
                temporary_contact,
            )

            motion_duration = args.motion_frames / 60
            motions = []
            for timestamp, final_path, temporary_path in zip(
                args.focus_time,
                motion_paths,
                temporary_motions,
            ):
                start, end = make_motion_strip(
                    input_path,
                    timestamp,
                    motion_duration,
                    args.motion_frames,
                    args.tile_width,
                    crop,
                    temporary_path,
                )
                motions.append(
                    {
                        "path": str(final_path),
                        "focus_time_seconds": timestamp,
                        "start_seconds": start,
                        "end_seconds": end,
                        "frames": args.motion_frames,
                        "sampling_fps": 60,
                    }
                )

            manifest = {
                "input": str(input_path),
                "duration_seconds": duration,
                "crop": crop,
                "contact_sheet": {
                    "path": str(contact_path),
                    "columns": args.columns,
                    "rows": args.rows,
                    "sample_times_seconds": sample_times,
                },
                "motion_strips": motions,
            }
            temporary_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            if inspect_path(output_dir) != ("directory", output_identity):
                raise ValueError(f"output directory changed while QA generation was running: {output_dir}")
            for temporary_path, final_path in zip(
                [temporary_contact, *temporary_motions, temporary_manifest],
                final_paths,
            ):
                install_artifact(temporary_path, final_path, initial_states[final_path])
    except (FileExistsError, RuntimeError, ValueError) as exception:
        return error(str(exception))

    print(f"[ok] contact sheet: {contact_path}")
    for path in motion_paths:
        print(f"[ok] motion strip: {path}")
    print(f"[ok] QA manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
