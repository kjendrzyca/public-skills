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

### [`ask-claude`](./skills/ask-claude)

Delegate focused analysis, execution-plan review, code review, or second-opinion work to Claude Code through non-interactive `claude -p`.

This skill is intentionally small: it standardizes the prompt shape and safe default command so another agent can consult Claude without opening an interactive session.

### [`coding-consult-design`](./skills/coding-consult-design)

Run a structured, repository-grounded design consultation with Codex CLI or Claude Code for non-trivial software problems, proposed fixes, and execution plans.

The consultant works read-only, receives a concrete evidence packet and numbered decision questions, and defaults to the other model family to reduce correlated blind spots.

### [`battery-stats`](./skills/battery-stats)

Check macOS laptop battery telemetry, current power drain, average screen-on watt usage, health, cycle count, and recent real-world battery runtime from local `pmset`, `ioreg`, `system_profiler`, and power-management logs.

The bundled script produces a concise human report by default and JSON when another agent needs structured battery statistics.

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
