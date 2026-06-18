---
name: handoff
description: Compact the current conversation into a handoff document for another agent to continue from. Use when the user asks for a handoff, session transfer, continuation note, context summary for a fresh agent, or a document describing what the next session should pick up.
license: MIT
---

# Handoff

Write a compact handoff document so a fresh agent can continue the work without replaying the full conversation.

## Workflow

1. Identify the next-session focus from the user's request. If the user included a focus phrase or arguments, treat that as the intended focus and tailor the handoff to it.
2. Write the document to the user's OS temporary directory, not the current workspace.
   - On macOS/Linux, use `$TMPDIR` when set, otherwise `/tmp`.
   - On Windows, use `%TEMP%`.
   - Use a clear filename such as `handoff-YYYYMMDD-HHMMSS.md`.
3. Keep the handoff self-contained enough for continuation, but do not duplicate material already captured in artifacts such as PRDs, plans, ADRs, issues, commits, diffs, or reports. Reference those artifacts by path or URL instead.
4. Redact sensitive information, including API keys, passwords, tokens, private auth material, personal identifiers, and any content the user clearly did not intend to hand to another agent.
5. Do not start the continuation work. Produce the handoff file and report its path.

## Document Shape

Include these sections when relevant:

- `Purpose`: what the next agent should focus on.
- `Current State`: where the work stands now.
- `Completed Work`: concise bullets for what was already done.
- `Key Artifacts`: paths, URLs, PRs, issues, commits, plans, reports, or diffs to inspect instead of duplicated content.
- `Decisions And Constraints`: important choices, assumptions, style rules, safety constraints, and open questions.
- `Suggested Skills`: skill names the next agent should invoke, with one short reason each.
- `Next Steps`: ordered continuation steps.
- `Verification`: checks already run, checks still needed, and known blockers.

Prefer concrete paths, command names, and status facts over narrative detail. If a fact is uncertain, mark it as uncertain instead of filling the gap.
