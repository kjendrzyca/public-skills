# Public Skills

A collection of reusable [Agent Skills](https://agentskills.io) compatible with Claude, Codex, OpenCode, and other agents that support the spec.

## Installation

Install a single skill into your agent environment:

```bash
npx skills add github.com/kjendrzyca/public-skills --skill <skill-name>
```

Target a specific agent:

```bash
npx skills add github.com/kjendrzyca/public-skills --skill <skill-name> --agent opencode
```

## Available Skills

### [`diff-explainer`](./skills/diff-explainer)

Explain GitHub pull requests from a PR URL as grouped Markdown diff reports with per-group explanations, important snippets, and PR Files links.

Demo: [watch a short diff-explainer demo](./assets/diff-explainer-demo.mp4).

### [`video-analysis`](./skills/video-analysis)

Analyze local video or audio files with ffmpeg/ffprobe, Parakeet MLX or Whisper transcription, contact sheets, and timestamped issue notes.

## Contributing

See [AGENTS.md](./AGENTS.md) for authoring rules.

## License

[MIT](./LICENSE)
