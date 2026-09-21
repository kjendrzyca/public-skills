# Shared MCP session

Source: [MCPorter daemon](https://github.com/openclaw/mcporter/blob/main/docs/daemon.md)
Checked: 2026-09-21; tested locally with MCPorter 0.13.13.

`lifecycle: keep-alive` routes calls through MCPorter's local daemon. The daemon
retains the HTTP connection between CLI processes. Tally's working form lives in
that MCP session, so keep this setting and use the same config throughout a task.

Equivalent callers share the connection. Each CLI invocation finishing does not
release the working form. Daemon status is available through
`mcporter daemon status --json`. A daemon restart or lost connection can discard
unsaved work. Do not restart the shared daemon as an automatic retry.

## Session coordination

This cooperative lock coordinates agents following this skill; MCPorter does
not enforce it. Callers that ignore the lock can still replace the working form.
Before loading/creating a working form or reading/editing its blocks, acquire:

```bash
mkdir -p "$HOME/.mcporter"
mkdir "$HOME/.mcporter/tally-edit.lock"
```

If the second command fails because the directory exists, another workflow owns
the working form. Read its `owner.txt`, report the conflict, and do not call
session tools or remove someone else's lock. On success, write your agent/session
identifier and task in `owner.txt` inside the lock directory.

Hold ownership across separate CLI calls, including save and post-save checks.
Before saving, compare `list_blocks` with the intended form. If state is missing
or unexpected, stop before `save_form`; recover from saved content and the task's
local input after resolving ownership or connection loss.

Release only your own lock after successful verification or deliberate abandonment:

```bash
rm "$HOME/.mcporter/tally-edit.lock/owner.txt"
rmdir "$HOME/.mcporter/tally-edit.lock"
```

When abandoning unsaved edits, report that they were not persisted. The next
owner must start by loading/creating its own form. Read-only form/workspace lists,
submissions, and analytics do not select a working form and need no session lock.
