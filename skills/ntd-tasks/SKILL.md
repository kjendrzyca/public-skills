---
name: ntd-tasks
description: Fetch and manage NoThinkDo tasks. Works only with the NoThinkDo app (https://nothinkdo.app) and requires an account there. Use this when the user asks about their tasks, wants to create/update/complete/delete tasks, or needs to see their task list.
compatibility: Requires a NoThinkDo (https://nothinkdo.app) account and an agent token stored in macOS Keychain. Scripts need Node.js and network access to nothinkdo.app.
allowed-tools: Bash(scripts/ntd-run.sh *)
---

# NoThinkDo Task Management

This skill is a companion to [NoThinkDo](https://nothinkdo.app), a minimalist daily task app with a hard 5-task daily limit. It only works with a NoThinkDo account; without one it has nothing to talk to.

## Setup

1. Sign in at https://nothinkdo.app and generate an agent token: Account -> Agent Tokens.
2. Store the token in macOS Keychain (paste it when prompted):

```bash
bash -lc 'read -rsp "Paste NTD token: " TOKEN && echo && security add-generic-password -s "ntd-agent-token" -a "ntd" -w "$TOKEN" -U && unset TOKEN'
```

Tokens are ephemeral: the server loses them on every deploy or restart, so regenerate and re-store when commands start failing with auth errors.

## Commands

```bash
# List all active (uncompleted) tasks
scripts/ntd-run.sh list

# List by view: inbox, today, upcoming, archive
scripts/ntd-run.sh list --view today

# Create a task (inbox — no date)
scripts/ntd-run.sh create '{"title":"Review PR #42"}'

# Create a task with a date and description
scripts/ntd-run.sh create '{"title":"Write migration guide", "date":"2026-03-20", "description":"Cover breaking changes in v2 API"}'

# Update a task
scripts/ntd-run.sh update '{"id":"<task-id>", "title":"Updated title"}'

# Mark task as completed
scripts/ntd-run.sh complete <task-id>

# Delete a task (soft delete)
scripts/ntd-run.sh delete <task-id>
```

## Task Structure

Tasks have these fields:

- `id` — unique identifier (UUID)
- `title` — task title (required)
- `description` — optional longer description
- `date` — optional calendar-day string `"yyyy-MM-dd"` (see Dates below). Tasks without a date go to Inbox
- `completed` — boolean
- `createdAt` — ISO timestamp
- `lastUpdatedAt` — ISO timestamp
- `completedOn` — calendar-day string `"yyyy-MM-dd"` or null (the day the task was completed; timezone-free)
- `order` — numeric sort order
- `deleted` — soft-delete flag

Tasks synced from older app versions may still carry a legacy `completedAt` ISO timestamp instead of `completedOn`, and a legacy `date` stored as a full ISO instant. The CLI normalizes such records right after decryption using the same rule as the app (legacy instants are interpreted in `Europe/Warsaw`, the timezone the historical data was created in), so views, the daily limit, and updates always agree with the app. You never need to handle the legacy shape yourself.

## Views

- **inbox** — tasks without a date
- **today** — tasks with today's date (uncompleted only)
- **upcoming** — tasks with a future date (uncompleted only)
- **archive** — completed tasks

## Dates

Dates must be ISO format strings. Convert natural language to ISO before passing:

- "today" -> `"2026-03-20"` (use current date)
- "tomorrow" -> `"2026-03-21"` (current date + 1)
- "next Monday" -> compute and use `"YYYY-MM-DD"`

The `date` field accepts both short (`"2026-03-20"`) and full (`"2026-03-20T00:00:00.000Z"`) ISO formats; full ISO inputs are converted to the local calendar day and stored as `"yyyy-MM-dd"`.

## Limits

- Maximum **5 tasks per day** (burnout prevention)

## Environment

Token is stored in macOS Keychain and read automatically by `ntd-run.sh`.
No manual environment variable setup is required.

## Output

All commands return JSON. `list` returns an array, all others return a single task object.
