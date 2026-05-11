#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"[error] input not found: {input_path}", file=sys.stderr)
        return 1

    if shutil.which("ffprobe") is None:
        print("[error] ffprobe is required but was not found on PATH", file=sys.stderr)
        return 1
    if shutil.which("ffmpeg") is None:
        print("[error] ffmpeg is required but was not found on PATH", file=sys.stderr)
        return 1

    output_dir = resolve_output_dir(args, input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    print(f"[info] input: {input_path}")
    print(f"[info] output: {output_dir}")

    try:
        metadata = probe_metadata(input_path)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        message = describe_command_error(error)
        write_analysis_error(
            output_dir=output_dir,
            input_path=input_path,
            title="Could not inspect media metadata",
            detail=message,
        )
        print(f"[error] ffprobe failed; see {output_dir / 'analysis-error.md'}")
        return 1
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_metadata_markdown(metadata, output_dir / "metadata.md")

    duration = media_duration(metadata)
    has_audio = any(
        stream.get("codec_type") == "audio" for stream in metadata.get("streams", [])
    )

    transcript_status = "skipped"
    audio_path = output_dir / "audio.wav"
    if has_audio and not args.no_transcript:
        audio_status = extract_audio(input_path, audio_path, output_dir)
        if audio_status == "ok":
            transcript_status = transcribe_audio(audio_path, output_dir)
            write_transcript_markdown(output_dir)
        else:
            transcript_status = audio_status
    elif not has_audio:
        transcript_status = "skipped: no audio stream"

    broad_frames = []
    if duration is not None and duration > 0:
        times = sample_times(
            duration=duration,
            interval=args.sample_interval,
            max_frames=args.max_contact_frames,
        )
        broad_frames = extract_frames(
            input_path=input_path,
            output_dir=frames_dir,
            times=times,
            prefix="sample",
            width=args.frame_width,
        )
        make_contact_sheet(
            broad_frames,
            output_dir / "contact-sheet.jpg",
            tile_cols=args.tile_cols,
        )
    else:
        print("[warn] duration unavailable; skipping sampled contact sheet")

    checkpoint_frames = []
    if args.timestamps:
        checkpoint_times = [parse_timestamp(value) for value in args.timestamps]
        checkpoint_frames = extract_frames(
            input_path=input_path,
            output_dir=frames_dir,
            times=checkpoint_times,
            prefix="checkpoint",
            width=args.frame_width,
        )

    focus_dirs = []
    for index, raw_window in enumerate(args.focus_window, start=1):
        start, end = parse_window(raw_window)
        if end <= start:
            print(f"[warn] ignoring invalid focus window: {raw_window}")
            continue
        focus_dir = output_dir / f"focus-{index:02d}-{timestamp_for_filename(start)}-to-{timestamp_for_filename(end)}"
        focus_dir.mkdir(exist_ok=True)
        times = []
        current = start
        while current <= end:
            times.append(current)
            current += args.focus_interval
        focus_frames = extract_frames(
            input_path=input_path,
            output_dir=focus_dir,
            times=times,
            prefix="focus",
            width=args.focus_frame_width,
        )
        if focus_frames:
            make_contact_sheet(
                focus_frames,
                focus_dir / "contact-sheet.jpg",
                tile_cols=args.tile_cols,
            )
            focus_dirs.append(focus_dir)

    write_issue_notes(
        output_dir=output_dir,
        input_path=input_path,
        metadata=metadata,
        transcript_status=transcript_status,
        broad_frames=broad_frames,
        checkpoint_frames=checkpoint_frames,
        focus_dirs=focus_dirs,
    )

    print("[ok] video analysis artifacts ready")
    print(f"[ok] issue notes scaffold: {output_dir / 'issue-notes.md'}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a local video/audio file with metadata, transcript, frames, and notes."
    )
    parser.add_argument("--input", required=True, help="Path to a video or audio file.")
    parser.add_argument(
        "--output-dir",
        help="Directory for artifacts. Defaults to .agent-data/video-analysis/<input-name>.",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=5.0,
        help="Seconds between broad sampled frames. Default: 5.",
    )
    parser.add_argument(
        "--max-contact-frames",
        type=int,
        default=40,
        help="Maximum broad frames before the script widens the interval. Default: 40.",
    )
    parser.add_argument(
        "--frame-width",
        type=int,
        default=735,
        help="Width for broad/checkpoint frames. Default: 735.",
    )
    parser.add_argument(
        "--focus-frame-width",
        type=int,
        default=588,
        help="Width for focused-window frames. Default: 588.",
    )
    parser.add_argument(
        "--focus-window",
        action="append",
        default=[],
        metavar="START,END",
        help="Focused window to sample, for example '75,110' or '00:01:15,00:01:50'. Repeatable.",
    )
    parser.add_argument(
        "--focus-interval",
        type=float,
        default=1.0,
        help="Seconds between focused-window frames. Default: 1.",
    )
    parser.add_argument(
        "--timestamps",
        nargs="*",
        default=[],
        help="Exact checkpoint timestamps, e.g. 00:01:25 93.5.",
    )
    parser.add_argument(
        "--tile-cols",
        type=int,
        default=5,
        help="Contact sheet columns when ImageMagick is available. Default: 5.",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Skip audio extraction/transcription.",
    )
    return parser.parse_args()


def resolve_output_dir(args: argparse.Namespace, input_path: Path) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    return (Path.cwd() / ".agent-data" / "video-analysis" / slugify(input_path.stem)).resolve()


def run_command(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("[cmd] " + shell_join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def probe_metadata(input_path: Path) -> dict:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(input_path),
        ]
    )
    return json.loads(result.stdout)


def write_metadata_markdown(metadata: dict, output_path: Path) -> None:
    duration = media_duration(metadata)
    lines = ["# Media Metadata", ""]
    if duration is not None:
        lines.append(f"- Duration: `{format_timestamp(duration)}` ({duration:.3f}s)")
    format_info = metadata.get("format", {})
    if format_info.get("format_name"):
        lines.append(f"- Format: `{format_info['format_name']}`")
    if format_info.get("bit_rate"):
        lines.append(f"- Bitrate: `{format_info['bit_rate']}`")
    lines.append("")
    lines.append("## Streams")
    lines.append("")
    for stream in metadata.get("streams", []):
        index = stream.get("index", "?")
        codec_type = stream.get("codec_type", "unknown")
        codec = stream.get("codec_name", "unknown")
        line = f"- Stream `{index}`: `{codec_type}` / `{codec}`"
        if codec_type == "video":
            width = stream.get("width")
            height = stream.get("height")
            fps = stream.get("avg_frame_rate")
            line += f", {width}x{height}, fps `{fps}`"
        if codec_type == "audio":
            sample_rate = stream.get("sample_rate")
            channels = stream.get("channels")
            line += f", {channels} channel(s), {sample_rate} Hz"
        lines.append(line)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def media_duration(metadata: dict) -> float | None:
    candidates = []
    format_duration = metadata.get("format", {}).get("duration")
    if format_duration is not None:
        candidates.append(format_duration)
    for stream in metadata.get("streams", []):
        if stream.get("duration") is not None:
            candidates.append(stream["duration"])
    for value in candidates:
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def extract_audio(input_path: Path, audio_path: Path, output_dir: Path) -> str:
    result = run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ],
        check=False,
    )
    if result.returncode == 0 and audio_path.exists():
        return "ok"
    detail = describe_completed_process(result)
    (output_dir / "audio-extraction-error.md").write_text(
        "# Audio Extraction Failed\n\n" + detail,
        encoding="utf-8",
    )
    print("[warn] audio extraction failed; continuing without transcript")
    return "failed: see audio-extraction-error.md"


def transcribe_audio(audio_path: Path, output_dir: Path) -> str:
    attempts = []

    direct_parakeet = shutil.which("parakeet-mlx")
    if direct_parakeet:
        attempts.append(
            [
                direct_parakeet,
                str(audio_path),
                "--output-dir",
                str(output_dir),
                "--output-format",
                "all",
                "--output-template",
                "transcript",
            ]
        )

    uv = shutil.which("uv")
    if uv:
        attempts.append(
            [
                uv,
                "run",
                "--with",
                "parakeet-mlx",
                "parakeet-mlx",
                str(audio_path),
                "--output-dir",
                str(output_dir),
                "--output-format",
                "all",
                "--output-template",
                "transcript",
            ]
        )

    whisper = shutil.which("whisper")
    if whisper:
        attempts.append(
            [
                whisper,
                str(audio_path),
                "--model",
                "turbo",
                "--output_dir",
                str(output_dir),
                "--output_format",
                "all",
            ]
        )

    uvx = shutil.which("uvx")
    if uvx:
        attempts.append(
            [
                uvx,
                "--from",
                "openai-whisper",
                "whisper",
                str(audio_path),
                "--model",
                "turbo",
                "--output_dir",
                str(output_dir),
                "--output_format",
                "all",
            ]
        )

    whisper_cli = shutil.which("whisper-cli")
    whisper_cpp_model = find_whisper_cpp_model()
    if whisper_cli and whisper_cpp_model:
        attempts.append(
            [
                whisper_cli,
                "-m",
                str(whisper_cpp_model),
                "-l",
                "auto",
                "-osrt",
                "-ovtt",
                "-otxt",
                "-oj",
                "-of",
                str(output_dir / "transcript"),
                str(audio_path),
            ]
        )

    errors = []
    for cmd in attempts:
        try:
            result = run_command(cmd, check=False)
        except OSError as error:
            errors.append(f"{cmd[0]}: {error}")
            continue
        if result.returncode == 0 and has_transcript_output(output_dir):
            return f"ok: {Path(cmd[0]).name}"
        errors.append(
            f"{Path(cmd[0]).name} exited {result.returncode}\n{result.stderr[-2000:]}"
        )

    message = "No transcription engine produced output.\n\n" + "\n\n".join(errors)
    (output_dir / "transcription-error.md").write_text(message, encoding="utf-8")
    print("[warn] transcription unavailable; see transcription-error.md")
    return "failed: see transcription-error.md"


def has_transcript_output(output_dir: Path) -> bool:
    return any(
        (output_dir / name).exists()
        for name in ["transcript.srt", "transcript.vtt", "transcript.txt", "transcript.json"]
    )


def find_whisper_cpp_model() -> Path | None:
    env_value = None
    try:
        import os

        env_value = os.environ.get("WHISPER_CPP_MODEL")
    except Exception:
        env_value = None
    if env_value:
        path = Path(env_value).expanduser()
        if path.exists():
            return path
    candidates = [
        Path.cwd() / "models" / "ggml-base.en.bin",
        Path.cwd() / "models" / "ggml-base.bin",
        Path.home() / ".cache" / "whisper.cpp" / "ggml-base.en.bin",
        Path("/opt/homebrew/share/whisper-cpp/ggml-base.en.bin"),
        Path("/usr/local/share/whisper-cpp/ggml-base.en.bin"),
    ]
    return next((path for path in candidates if path.exists()), None)


def write_transcript_markdown(output_dir: Path) -> None:
    srt_path = output_dir / "transcript.srt"
    if not srt_path.exists():
        return
    blocks = consolidate_transcript_blocks(
        parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    )
    lines = ["# Transcript", ""]
    for start, end, text in blocks:
        lines.append(f"- `{start} -> {end}` {text}")
    (output_dir / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_srt(content: str) -> list[tuple[str, str, str]]:
    blocks = re.split(r"\n\s*\n", content.strip())
    parsed = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_line = next((line for line in lines if "-->" in line), None)
        if time_line is None:
            continue
        start, end = [part.strip() for part in time_line.split("-->", 1)]
        text_lines = lines[lines.index(time_line) + 1 :]
        parsed.append((start, end, " ".join(text_lines)))
    return parsed


def consolidate_transcript_blocks(
    blocks: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Merge consecutive SRT blocks that carry the same phrase.

    Some transcription engines (e.g. parakeet-mlx with --highlight-words) emit
    one SRT entry per spoken word, repeating the whole sentence with HTML-like
    `<u>...</u>` markup around the currently-spoken word. Even without that
    flag, word-level engines can produce one block per word. This helper
    strips the markup, then merges runs of identical text into a single block
    spanning the run's full time range. Keeps single-block entries unchanged.
    """
    if not blocks:
        return blocks
    cleaned = [
        (start, end, re.sub(r"</?u>", "", text).strip()) for start, end, text in blocks
    ]
    consolidated: list[tuple[str, str, str]] = []
    for start, end, text in cleaned:
        if consolidated and consolidated[-1][2] == text:
            prev_start, _, prev_text = consolidated[-1]
            consolidated[-1] = (prev_start, end, prev_text)
        else:
            consolidated.append((start, end, text))
    return consolidated


def sample_times(duration: float, interval: float, max_frames: int) -> list[float]:
    interval = max(interval, 0.1)
    max_frames = max(max_frames, 1)
    estimated = math.floor(duration / interval) + 1
    if estimated > max_frames and max_frames > 1:
        interval = duration / (max_frames - 1)
    times = []
    current = 0.0
    while current <= duration and len(times) < max_frames:
        times.append(current)
        current += interval
    if not times:
        times.append(0.0)
    return times


def extract_frames(
    *,
    input_path: Path,
    output_dir: Path,
    times: list[float],
    prefix: str,
    width: int,
) -> list[Path]:
    frames = []
    for index, timestamp in enumerate(times, start=1):
        safe_time = timestamp_for_filename(timestamp)
        output_path = output_dir / f"{prefix}-{index:03d}-t-{safe_time}.jpg"
        result = run_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                format_timestamp(timestamp),
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-update",
                "1",
                "-vf",
                f"scale={width}:-1",
                str(output_path),
            ],
            check=False,
        )
        if result.returncode == 0 and output_path.exists():
            frames.append(output_path)
            continue
        write_frame_error(output_dir, timestamp, result)
        print(
            f"[warn] skipped {prefix} frame at {format_timestamp(timestamp)}; ffmpeg failed"
        )
    return frames


def write_frame_error(
    output_dir: Path,
    timestamp: float,
    result: subprocess.CompletedProcess[str],
) -> None:
    error_path = output_dir / "frame-extraction-errors.md"
    with error_path.open("a", encoding="utf-8") as handle:
        handle.write(f"## {format_timestamp(timestamp)}\n\n")
        handle.write(describe_completed_process(result))
        handle.write("\n\n")


def make_contact_sheet(frames: list[Path], output_path: Path, *, tile_cols: int) -> None:
    if not frames:
        return
    montage = shutil.which("montage")
    magick = shutil.which("magick")
    if montage is None and magick is None:
        print("[warn] ImageMagick not found; skipping contact sheet")
        return
    base_cmd = [montage] if montage else [magick, "montage"]
    cmd = [*base_cmd]
    font_path = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    if font_path.exists():
        cmd.extend(["-font", str(font_path)])
    cmd.extend(["-label", "%f"])
    cmd.extend(str(frame) for frame in frames)
    cmd.extend(["-tile", f"{tile_cols}x", "-geometry", "+8+8", str(output_path)])
    result = run_command(cmd, check=False)
    if result.returncode != 0:
        print("[warn] contact sheet failed; frames are still available")
        if result.stderr:
            print(result.stderr[-1000:])


def write_issue_notes(
    *,
    output_dir: Path,
    input_path: Path,
    metadata: dict,
    transcript_status: str,
    broad_frames: list[Path],
    checkpoint_frames: list[Path],
    focus_dirs: list[Path],
) -> None:
    duration = media_duration(metadata)
    lines = [
        "# Video Analysis Notes",
        "",
        "## Source",
        "",
        f"- Input: `{input_path}`",
        f"- Output directory: `{output_dir}`",
        f"- Transcript: `{transcript_status}`",
    ]
    if duration is not None:
        lines.append(f"- Duration: `{format_timestamp(duration)}` ({duration:.3f}s)")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- Metadata: `metadata.md`, `metadata.json`",
        ]
    )
    if (output_dir / "transcript.md").exists():
        lines.append("- Transcript: `transcript.md`, `transcript.srt`, `transcript.vtt`, `transcript.json`")
    if broad_frames:
        lines.append("- Broad contact sheet: `contact-sheet.jpg`")
    if checkpoint_frames:
        lines.append("- Checkpoint frames: `frames/checkpoint-*.jpg`")
    for focus_dir in focus_dirs:
        lines.append(f"- Focus window: `{focus_dir.relative_to(output_dir)}/contact-sheet.jpg`")
    lines.extend(
        [
            "",
            "## Timestamped Timeline",
            "",
        ]
    )
    transcript_blocks = []
    transcript_path = output_dir / "transcript.srt"
    if transcript_path.exists():
        transcript_blocks = consolidate_transcript_blocks(
            parse_srt(transcript_path.read_text(encoding="utf-8", errors="replace"))
        )
    if transcript_blocks:
        for start, end, text in transcript_blocks:
            lines.append(f"- `{start} -> {end}` {text}")
    else:
        lines.append("- Add timeline notes after reviewing frames and transcript artifacts.")
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "Use this shape for each finding:",
            "",
            "```markdown",
            "### [severity] Short Finding Title",
            "- Timestamp: [00:00:00.000-00:00:00.000]",
            "- Evidence: transcript quote and frame/contact-sheet path",
            "- Observed behavior: what happened on screen",
            "- User impact: why it matters",
            "- Likely cause: hypothesis, if supported by code or evidence",
            "- Suggested fix: concise action",
            "```",
            "",
            "## Open Questions",
            "",
            "- Add unresolved product or technical questions here.",
        ]
    )
    (output_dir / "issue-notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_analysis_error(
    *,
    output_dir: Path,
    input_path: Path,
    title: str,
    detail: str,
) -> None:
    lines = [
        "# Video Analysis Error",
        "",
        f"## {title}",
        "",
        f"- Input: `{input_path}`",
        f"- Output directory: `{output_dir}`",
        "",
        "```text",
        detail.strip(),
        "```",
    ]
    (output_dir / "analysis-error.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def describe_command_error(error: BaseException) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        return describe_completed_process(error)
    return str(error)


def describe_completed_process(
    result: subprocess.CompletedProcess[str] | subprocess.CalledProcessError,
) -> str:
    command = getattr(result, "cmd", None) or getattr(result, "args", [])
    stdout = (getattr(result, "stdout", None) or "").strip()
    stderr = (getattr(result, "stderr", None) or "").strip()
    return "\n".join(
        [
            f"Command: {shell_join([str(part) for part in command])}",
            f"Exit code: {getattr(result, 'returncode', 'unknown')}",
            "",
            "stderr:",
            stderr[-4000:] if stderr else "<empty>",
            "",
            "stdout:",
            stdout[-4000:] if stdout else "<empty>",
        ]
    )


def parse_window(raw: str) -> tuple[float, float]:
    if "," not in raw:
        raise ValueError(f"focus window must be START,END: {raw}")
    start_raw, end_raw = [part.strip() for part in raw.split(",", 1)]
    return parse_timestamp(start_raw), parse_timestamp(end_raw)


def parse_timestamp(raw: str) -> float:
    value = raw.strip()
    if not value:
        raise ValueError("empty timestamp")
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"unsupported timestamp: {raw}")


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round((seconds - math.floor(seconds)) * 1000))
    total_seconds = int(math.floor(seconds))
    if milliseconds == 1000:
        total_seconds += 1
        milliseconds = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def timestamp_for_filename(seconds: float) -> str:
    return format_timestamp(seconds).replace(":", "-").replace(".", "-")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "video"


def shell_join(cmd: list[str]) -> str:
    return " ".join(quote_arg(part) for part in cmd)


def quote_arg(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@%+-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
