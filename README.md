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

### [`handoff`](./skills/handoff)

Compact the current conversation into a redacted handoff document for another agent to continue from.

The handoff is saved to the operating system's temporary directory, not the current workspace, and points to existing artifacts instead of duplicating them.

### [`coding-explain-diff`](./skills/coding-explain-diff)

Explain GitHub pull requests from a PR URL as grouped Markdown diff reports with per-group explanations, important snippets, and PR Files links.

Demo: [watch a short coding-explain-diff demo](./assets/coding-explain-diff-demo.mp4).

### [`coding-explain-problem`](./skills/coding-explain-problem)

Explain software and code-related problems in simple terms, including bugs, feature requests, refactors, errors, PR intent, or the problem an existing piece of code solves.

This skill is intentionally super simple: it is a tiny prompt for quickly restating the problem in plain language, not a full review or analysis workflow.

### [`coding-audit-assumptions`](./skills/coding-audit-assumptions)

Reframe software problems, execution plans, architecture changes, bug fixes, and reliability issues by identifying the assumptions that make the failure mode possible, then proposing a design that removes, redesigns, or makes those assumptions irrelevant.

This skill is intentionally tiny: it is a prompt for breaking out of default solution paths before implementation starts.

### [`video-analysis`](./skills/video-analysis)

Analyze local video or audio files with ffmpeg/ffprobe, Parakeet MLX or Whisper transcription, contact sheets, and timestamped issue notes.

## Contributing

See [AGENTS.md](./AGENTS.md) for authoring rules.

## License

[MIT](./LICENSE)
