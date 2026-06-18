---
name: ask-claude
description: Delegate focused analysis, code review, execution-plan review, or second-opinion work to Claude Code through non-interactive `claude -p`. Use when an agent should consult Claude, ask for an independent review, cross-check code or a plan, or hand off a bounded read-only task without opening an interactive Claude session.
license: MIT
---

# Ask Claude

Use Claude Code as a bounded, non-interactive reviewer or consultant through `claude -p`. Keep the delegation self-contained, read-only by default, and impossible to stall on interactive prompts.

Requires Claude Code CLI (`claude`) on PATH with working auth.

## Defaults

- Use `claude -p` / `claude --print`, never plain interactive `claude`.
- Use `--model opus` by default. This targets Claude Code's current Opus alias; the intended default is Opus 4.8 / latest Opus.
- Use `--effort max`.
- Use `--no-session-persistence` unless the user explicitly wants a saved Claude session.
- Use `--permission-mode dontAsk` so missing permissions fail closed instead of waiting for a prompt.
- Disable tools with `--tools ""` unless Claude must inspect local files.
- Do not use `--continue`, `--resume`, or an existing session for delegation.
- Run only from a trusted directory. In print mode Claude skips the workspace trust dialog.

## Preflight

Before the first use in a session, verify the local CLI supports the flags this skill depends on:

```bash
command -v claude
claude --help | rg -- '--model|--effort|--permission-mode|--tools|--allowedTools|--add-dir|--no-session-persistence|--output-format'
```

If any required flag is missing, stop and report the installed Claude Code version and missing flag. Do not invent alternate flags from model memory.

## Prompt Shape

Make the prompt do all of this:

- State Claude's role: independent reviewer, execution-plan reviewer, code reviewer, or consultant.
- Give the exact task and the concrete artifact or context to inspect.
- Say what output you need: findings, risks, missing tests, alternative design, or a concise verdict.
- Tell Claude to avoid changing files unless the user explicitly delegated implementation.
- Tell Claude to stop and report missing context instead of asking interactive follow-up questions.
- Keep the output bounded enough that Codex can read and synthesize it.

## Consultation Command

Use this when you can paste the relevant context into the prompt. This is the safest default.

```bash
cat <<'PROMPT' | claude -p \
  --model opus \
  --effort max \
  --permission-mode dontAsk \
  --tools "" \
  --no-session-persistence \
  --output-format text
You are Claude Code acting as an independent reviewer for another agent.

Task:
[specific question or review request]

Context:
[paste the relevant plan, diff summary, code snippet, logs, or constraints]

Output:
- Start with the direct verdict or highest-risk findings.
- Give evidence for each point.
- If the context is insufficient, say exactly what is missing.
- Do not ask follow-up questions.
- Do not modify files.
PROMPT
```

## Read-Only Repo Command

Use this only when Claude must inspect files in the current repository. Keep the allowed tool surface actually read-only: `Read`, `Grep`, and `Glob` only.

If Claude needs git diff, status, logs, generated artifacts, or command output, Codex should collect that context and paste it into the prompt instead of granting Claude `Bash`. Do not describe a command as read-only if it can mutate files or external state.

```bash
cat <<'PROMPT' | claude -p \
  --model opus \
  --effort max \
  --permission-mode dontAsk \
  --tools Read,Grep,Glob \
  --allowedTools Read,Grep,Glob \
  --add-dir "$PWD" \
  --no-session-persistence \
  --output-format text
You are Claude Code acting as an independent read-only reviewer for another agent.

Task:
[specific code review, plan review, or investigation request]

Repository:
- Work only in the current directory.
- Inspect files as needed.
- Do not edit files.
- You do not have Bash access. If shell output is needed, say exactly what command output would help.
- If the read-only tools are insufficient, say what additional context would be needed.

Output:
- Start with findings or the direct verdict.
- Include file paths and line numbers when relevant.
- Distinguish confirmed facts from hypotheses.
- Do not ask follow-up questions.
PROMPT
```

## No-Stall Rules

- Always run `claude -p` through an agent shell tool with an explicit timeout or active polling plan.
- For a simple consultation, expect minutes, not an open-ended session. For a repo review, choose a bounded limit appropriate to the diff size.
- If the shell tool returns a live process/session, keep polling until it exits or terminate it through the tool's normal mechanism. Do not finish the user task while the Claude process is still running.
- Capture stderr and check the exit code. A non-zero exit means tool failure, not Claude's review. Report the exact stderr and command shape.
- If Claude exits with auth, model, budget, permission, or tool errors, report the exact blocker. Do not retry with broader tools, bypass permissions, or write access unless the user explicitly approves.
- Treat Claude's output as advice from another reviewer, not as ground truth. Check claims against local files before making changes based on them.
