---
name: coding-explain-problem
description: Explain coding problems, code behavior, review findings, architecture, or proposed changes in plain language. Use when the user asks what code does, why it exists, why a bug occurs, how existing behavior differs from a current change, or requests an explanation suitable for someone new to a codebase.
---

# Explain coding problems

Assume the user is new to the codebase unless they say otherwise.

- Lead with the plain-language answer.
- Separate existing behavior from behavior added or changed by the current task or pull request.
- Explain the runtime flow in short steps.
- Use one concrete example with realistic input and output when it helps.
- Define project-specific terms on first use.
- State when the issue applies and when it does not.
- Separate confirmed code facts from assumptions.
- End with the smallest reasonable fix and what remains unchanged.
- Avoid buzzwords and unexplained architecture terms.
- Keep the first explanation concise, but include enough context to explain why the code exists.
