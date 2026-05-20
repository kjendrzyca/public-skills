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

### [`explain-software-problem`](./skills/explain-software-problem)

Explain software and code-related problems in simple terms, including bugs, feature requests, refactors, errors, PR intent, or the problem an existing piece of code solves.

This skill is intentionally super simple: it is a tiny prompt for quickly restating the problem in plain language, not a full review or analysis workflow.

### [`video-analysis`](./skills/video-analysis)

Analyze local video or audio files with ffmpeg/ffprobe, Parakeet MLX or Whisper transcription, contact sheets, and timestamped issue notes.

## Contributing

See [AGENTS.md](./AGENTS.md) for authoring rules.

## License

[MIT](./LICENSE)
