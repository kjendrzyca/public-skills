---
name: coding-audit-assumptions
description: Think out of the box about a software problem or planned solution by questioning the assumptions that make it hard, then propose a different way to solve it - often simpler, with less work and less code. Use ONLY when the user explicitly invokes this skill or asks for it by name. Never trigger it automatically or as an internal step of planning, review, or remediation. Its proposals are options for the user to assess, never decisions to implement.
disable-model-invocation: true
license: MIT
---

# Audit Assumptions

Rethink the problem instead of solving it head-on. The unconventional part is the thinking, not the result: question the assumptions that make the problem (or the planned complexity) exist, and a different, better way to solve it may appear. The alternative itself can be trivially simple, boring, or just different - it only has to solve the problem better.

## Main goal: hit the root, simplify

A good proposal hits the root of the problem and simplifies or outright dissolves it - so well that nothing better is possible in the current state. Usually that means less work, less code, and fewer moving parts. Do not chase cleverness; chase the shortest path to a solved problem.

Judge proposals by how completely they dissolve the problem, not by line count. Sometimes the better solution needs more code, an extra mechanism, or persistent state - that is fine when it removes the reason the problem exists. What fails this skill is complexity that only hardens the current approach against symptoms while the root cause stays.

## Invocation rule (hard)

- Run this skill only when the human invoked it or explicitly asked for it in the current request.
- Never run it automatically, proactively, or as a step inside another workflow.
- "The task could benefit from it" is not an invocation.

## Method

1. State the problem in one sentence, as the user gave it.
2. List the assumptions that make the problem or the planned complexity possible.
3. For each assumption, ask: can it be removed, redesigned, or made irrelevant?
4. Propose one or more alternatives that solve the stated problem better - usually with less.
5. Critically assess each proposal yourself: is it genuinely adequate, or only clever-sounding? Name its weaknesses and what it gives up.

## Output rule (hard)

- Present the proposals to the human for assessment, with your critical evaluation attached.
- Treat every proposal as speculative until the human accepts it.
- Do not implement a proposal, fold it into a plan, or treat it as a requirement without explicit human approval.
