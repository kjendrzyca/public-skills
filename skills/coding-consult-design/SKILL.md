---
name: coding-consult-design
description: Use this skill for a structured, repository-grounded consultation with Codex CLI or Claude Code on a non-trivial software problem, proposed fix, design decision, implementation plan, or execution plan. Trigger when the user asks to consult Codex or Claude, get a deep second opinion, or stress-test an approach and the consultant should inspect repository evidence, answer multiple decision questions, and have its advice verified before action. Do not use for routine code review or a small single-question delegation. Run the other model family read-only by default.
---

# Consult Another Coding Agent

Turn the current work into a concrete consultation for a second frontier agent.
Give the consultant enough repository evidence to challenge the reasoning rather
than merely react to a summary.

Keep the consultation read-only. The calling agent remains responsible for the
decision, any implementation, and the final answer to the user.

Use this workflow when the decision benefits from an evidence packet and a
structured set of questions. For a small Claude-only question with all context
already supplied, use a simpler bounded delegation workflow if one is
available. For a review of an already-finished diff, use a dedicated code review
workflow unless the user is asking about the underlying design.

## Choose the consultant

Honor an explicit user choice. Otherwise, prefer the other model family to
reduce correlated blind spots:

| Calling agent | Consultant | Model | Effort |
| --- | --- | --- | --- |
| Claude Code | Codex CLI | `gpt-5.6-sol` | `xhigh` |
| Codex or another agent | Claude Code | `claude-fable-5` | `xhigh` |

Use these explicit defaults. Do not silently switch models, enable automatic
fallback, or reduce reasoning effort. If a model is unavailable, report the
exact error and ask the user to choose a replacement.

## Ground the consultation

Build the consultation from the current conversation and repository. Do not ask
the user to restate context that is already available.

1. Read the repository instructions and the artifacts that define the current
   problem: plans, relevant modules, tests, docs, and configuration.
2. Inspect the current worktree when it matters. Collect `git status`, the
   relevant diff, recent decisions, failing output, reproduction steps, and
   observed behavior. Claude's read-only tool set cannot run Git, so include
   exact relevant Git output in its prompt.
3. Separate confirmed facts from hypotheses. Include concrete evidence such as
   paths, symbols, error text, timings, or reproduction conditions.
4. State the proposed mechanism precisely. Name what changes, what stays the
   same, and the invariants that must survive.
5. Turn uncertainty into numbered questions. Include suspected failure modes,
   but always ask for missed holes and better alternatives too.

Point the consultant at real files with relative paths and explain what each
file establishes. Do not paste or paraphrase large code sections when the
consultant can inspect them directly. Include exact snippets or diffs only when
they are uncommitted, generated, external to the repository, or otherwise not
available through read-only file access.

## Write the prompt

Adapt this structure to the task. Omit sections that genuinely do not apply,
but preserve the distinction between evidence, proposal, constraints, and
questions.

```text
You are an independent senior software engineering consultant. Analyze this
repository read-only. Do not edit files or implement the change.

REPOSITORY AND DECISION
- Repository: <one-sentence description>
- Decision needed: <the exact problem, plan, or proposed change to assess>

READ FIRST
- <relative/path>: <what this file establishes; relevant section or symbol>
- <relative/path>: <what this file establishes; relevant section or symbol>

CURRENT STATE
- <what exists and how it behaves today>
- <relevant worktree/diff state and prior decisions>

PROBLEM AND EVIDENCE
- <observable failure, limitation, or design pressure>
- <reproduction, errors, measurements, or concrete examples>
- <confirmed facts versus current hypotheses>

PROPOSED CHANGE OR PLAN
- <mechanism, data flow, ownership, ordering, or lifecycle>
- <what changes and what explicitly remains unchanged>

CONSTRAINTS AND INVARIANTS
- <compatibility, safety, product, migration, or scope constraint>
- <invariants the solution must preserve>

QUESTIONS
1. What is your direct verdict on the proposed direction, and why?
2. What correctness holes or failure modes have we missed? Consider <specific
   suspected races, edge cases, lifecycle transitions, or cross-tool behavior>.
3. Which assumptions are weak or unsupported by the repository evidence?
4. Is the chosen mechanism better than <real alternative>? Explain the tradeoff.
5. What tests, migration, observability, rollback, or documentation implications
   should be part of the plan?
6. What important question have we failed to ask?

REQUIRED OUTPUT
- Start with the highest-impact findings and a direct verdict.
- Answer every numbered question explicitly.
- Cite relative file paths and line numbers or symbols where relevant.
- Distinguish confirmed facts from hypotheses.
- Identify missing context instead of inventing facts.
- Be as detailed as the decision requires; do not impose an arbitrary word cap.
- Do not provide implementation code unless a question explicitly asks for it.
```

For a problem without a proposed solution, replace `PROPOSED CHANGE OR PLAN`
with the candidate explanations or approaches under consideration. For a plan
review, include the plan plus the implementation and tests that constrain it.
For a bug investigation, emphasize reproduction evidence, the suspected cause,
and competing explanations.

## Preflight the CLI

Before the first consultation in a session, verify the selected CLI and every
required flag from its live help:

```bash
command -v codex
codex exec --help | rg -- '--model|--sandbox|--ephemeral|--cd|--output-last-message'

command -v claude
claude --help | rg -- '--model|--effort|--permission-mode|--tools|--allowedTools|--add-dir|--no-session-persistence|--output-format'
```

If the selected command or a required flag is missing, stop and report the
installed version and the missing requirement. Do not invent replacement flags
from memory.

## Run read-only

Run from the repository root. Store the prompt, full output, and logs in a fresh
temporary directory outside the repository so the consultation does not dirty
the worktree.

```bash
CONSULT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/coding-consult-design.XXXXXX")"
```

Save the completed prompt as `$CONSULT_DIR/prompt.md`, then use one backend.

### Codex CLI

```bash
codex exec \
  --cd "$PWD" \
  --sandbox read-only \
  --ephemeral \
  --skip-git-repo-check \
  --model gpt-5.6-sol \
  --config 'model_reasoning_effort="xhigh"' \
  --output-last-message "$CONSULT_DIR/consult-codex.md" \
  - < "$CONSULT_DIR/prompt.md" \
  > "$CONSULT_DIR/codex.log" 2>&1
```

### Claude Code

```bash
claude -p \
  --model claude-fable-5 \
  --effort xhigh \
  --permission-mode dontAsk \
  --tools Read,Grep,Glob \
  --allowedTools Read,Grep,Glob \
  --add-dir "$PWD" \
  --no-session-persistence \
  --output-format text \
  < "$CONSULT_DIR/prompt.md" \
  > "$CONSULT_DIR/consult-claude.md" \
  2> "$CONSULT_DIR/claude.log"
```

Do not grant edit, write, or unrestricted shell tools for consultation. If the
consultant needs command output, collect that read-only evidence in the calling
agent and run a focused follow-up consultation.

## Supervise and assess

- Run with an explicit time budget appropriate to the task. About 15 minutes is
  a sensible starting point for an xhigh consultation over a focused set of
  files.
- If the shell returns a live process, poll it until completion or terminate it
  at the agreed limit. Never leave a consultation process running after the
  task ends.
- Check the exit code and logs. A non-zero exit is a tool failure, not a review
  verdict.
- Read the full answer. Verify cited files, symbols, behavior, and claimed risks
  against the repository.
- Classify each material recommendation as accepted, rejected, or deferred,
  with a reason. Surface genuine decision points to the user.
- Apply changes only when the user's request authorizes implementation. The
  consultant's answer does not expand the task's scope or mutation authority.
- Report the backend, exact model and effort, output path, direct verdict, and
  how the advice affected the decision.
