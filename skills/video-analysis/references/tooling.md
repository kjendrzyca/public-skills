# Tooling

Use this reference when media tooling is missing or transcription fails.

## Required Tools

`ffmpeg` and `ffprobe` are required. Verify with:

```bash
ffmpeg -version
ffprobe -version
```

On macOS, install with Homebrew:

```bash
brew install ffmpeg imagemagick
```

ImageMagick is optional. Without it, the script still extracts frames but skips contact-sheet assembly.

## Transcription Engines

Preferred path:

```bash
uv run --with parakeet-mlx parakeet-mlx audio.wav --output-format all
```

This uses Parakeet MLX on Apple Silicon without requiring a global package install.

Fallbacks supported by `scripts/analyze-video.py`:

- `parakeet-mlx` if installed globally.
- `uv run --with parakeet-mlx parakeet-mlx` if `uv` is installed.
- `whisper` from OpenAI Whisper if installed globally.
- `uvx --from openai-whisper whisper` if `uvx` is installed.
- `whisper-cli` from whisper.cpp if `WHISPER_CPP_MODEL` points at a model file or a common model path exists.

For whisper.cpp, set:

```bash
export WHISPER_CPP_MODEL=/path/to/ggml-base.en.bin
```

## Pragmatic Defaults

- Use 5-second broad frames for recordings under 5 minutes.
- Use 10-15-second broad frames for longer product demos.
- Use 1-second focused frames around a reported bug window.
- Keep generated artifacts out of version control (the default output path is `.agent-data/video-analysis/`).

## Known Limitations (future work)

Parakeet-MLX (the default engine) tends to phoneticize less-common brand and product names when the speaker uses non-English phonology for English terms. Common cases: `Vercel` -> `Wersel`, `Hetzner` -> `Hecner`, `Neovim` -> `Neowim`, `Shure` -> `szure`. Standard tech acronyms (CLI, API, GPU, GitHub Actions, TypeScript, Kubernetes, etc.) come through cleanly. If brand-name fidelity matters for the downstream use case, two improvements are worth considering:

- An `--engine` flag to force Whisper-turbo (more multilingual training data) instead of falling through engines in fixed order.
- A `--glossary` flag taking a path to a substitution table (`Wersel=Vercel`, `Hecner=Hetzner`, ...) applied as a post-process to the transcript artifacts.

Neither is implemented yet; this note captures the design direction.
