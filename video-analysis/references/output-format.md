# Output Format

Use this reference when turning video artifacts into a final answer, bug report, or implementation plan.

## Timestamped Analysis

Start with a compact timeline of what happened. Use exact timestamps from the transcript or frame filenames.

```markdown
## Timeline

- [00:00:05.360-00:00:22.720] User opens settings and starts the third-party integration flow.
- [00:01:04.800-00:01:27.520] User waits while the UI remains on the same step after granting permission.
```

## Findings

Order findings by severity and confidence. Each finding should be evidence-backed.

```markdown
### High: Flow stalls after permission grant

- Timestamp: [00:01:04.800-00:01:27.520]
- Evidence: `transcript.srt` line/quote plus `focus-01-.../contact-sheet.jpg`
- Observed behavior: the user completed the external permission step, but the in-app UI stayed on the pre-permission state.
- User impact: the user had to guess that reopening the view might unblock the flow.
- Likely cause: a long-running async process was tied to a UI surface that lost focus during the external permission prompt.
- Suggested fix: resume the pending operation when focus returns, or move long-running work out of the dismissible UI surface.
```

## Rules

- Do not state a root cause unless code or system behavior supports it.
- Call uncertain causes hypotheses.
- Include paths to local artifacts when the user may inspect them.
- Use the user's transcript quotes when they reveal confusion or intent.
- Keep recommendations concrete enough to turn into code tasks.
