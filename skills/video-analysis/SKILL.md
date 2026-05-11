---
name: video-analysis
description: Analyze local video or audio files with ffmpeg/ffprobe, Parakeet MLX or Whisper transcription, contact sheets, checkpoint frames, and timestamped issue notes. Use when reviewing screen recordings, product demo videos, QA recordings, onboarding videos, bug reports with video evidence, or when asked to transcribe audio, inspect media metadata, extract frames, or create a timestamped analysis script from a video.
compatibility: Requires ffmpeg and ffprobe on PATH. Optional: ImageMagick for contact sheets, plus one of parakeet-mlx, whisper, or whisper-cli for transcription.
---

# Video Analysis

Analyze a local media file pragmatically: capture metadata, transcribe speech, generate visual checkpoints, then produce timestamped notes that tie observations to evidence.

## Quick Start

Run the bundled orchestrator (paths are relative to this skill directory):

```bash
python3 scripts/analyze-video.py \
  --input "/absolute/path/to/recording.mov" \
  --output-dir ".agent-data/video-analysis/recording"
```

If the skill lives in a different location, adjust the script path accordingly (e.g. `python3 path/to/video-analysis/scripts/analyze-video.py ...`).

## Workflow

1. Inspect media metadata with `ffprobe` before assuming duration, streams, or frame rate.
2. Extract normalized mono 16 kHz audio with `ffmpeg` when an audio stream exists.
3. Transcribe with Parakeet MLX first. Fall back to Whisper when Parakeet is unavailable.
4. Generate a broad contact sheet at a practical interval, usually 5-10 seconds.
5. Generate focused 1-second frames around suspicious windows when the transcript or user report points to a timestamp.
6. Review transcript and frames together. Write facts first, then hypotheses.
7. Produce timestamped issue notes with exact evidence paths.

## Output Artifacts

The script writes artifacts under the chosen output directory:

- `metadata.json` and `metadata.md`: raw and readable media metadata.
- `audio.wav`: normalized extracted audio when the input has audio.
- `transcript.srt`, `transcript.vtt`, `transcript.txt`, `transcript.json`: transcription outputs when a transcription engine is available.
- `transcript.md`: compact timestamped transcript for agent review.
- `frames/`: sampled frames and checkpoint frames.
- `contact-sheet.jpg`: broad visual contact sheet.
- `focus-*/contact-sheet.jpg`: focused visual contact sheets for specific time windows.
- `issue-notes.md`: scaffold for the final timestamped analysis.

## Common Commands

Create broad evidence every 5 seconds and a focused window from 75s to 110s:

```bash
python3 scripts/analyze-video.py \
  --input "/path/to/recording.mov" \
  --sample-interval 5 \
  --focus-window "75,110"
```

Extract exact checkpoint frames without doing transcription:

```bash
python3 scripts/analyze-video.py \
  --input "/path/to/recording.mov" \
  --timestamps "00:01:25" "00:01:33.5" \
  --no-transcript
```

Limit frame volume for long recordings:

```bash
python3 scripts/analyze-video.py \
  --input "/path/to/long-demo.mp4" \
  --sample-interval 15 \
  --max-contact-frames 48
```

## Review Guidance

The primary deliverable is `issue-notes.md` in the output directory. Fill in the timeline and findings sections of the scaffold the script wrote, using the format from `references/output-format.md`. The chat reply should be a short TL;DR plus a pointer to the file, not the full analysis - the file is the artifact the user keeps and re-reads.

Read `references/output-format.md` before writing the final analysis. Read `references/tooling.md` when a tool is missing or transcription fails. Read `references/video-review-rubric.md` when deciding what to inspect in UX or bug-report recordings.

When reporting findings:

- Use timestamps like `[00:01:27.520]`.
- Link each finding to transcript text, frame files, or contact sheets.
- Distinguish observed behavior from inferred root cause.
- Prefer a few high-confidence issues over speculative commentary.
- Preserve user language from the transcript when it explains confusion or intent.

## Tooling Notes

The script expects `ffmpeg` and `ffprobe` on `PATH`. It tries Parakeet MLX via either `parakeet-mlx` or `uv run --with parakeet-mlx parakeet-mlx`. Whisper fallback supports `whisper`, `uvx --from openai-whisper whisper`, and `whisper-cli` when a local whisper.cpp model is discoverable or `WHISPER_CPP_MODEL` is set.
