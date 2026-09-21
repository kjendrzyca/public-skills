---
name: tally
description: Create and edit Tally.so forms and read responses.
license: MIT
---

# Tally

Use the official Tally MCP server through MCPorter. Resolve `mcporter.json`
relative to this `SKILL.md`, and set `TALLY_MCP_CONFIG` to that resolved absolute
path in each shell invocation (or export it in a persistent shell). Do not infer
it from the working directory. Examples below assume this variable is set.
The bundled config uses OAuth, keeps the connection alive, and disables imports
from other MCP clients. See [connection.md](references/connection.md) for setup.

## Discover only what you need

1. Read compact tool signatures:

   ```bash
   mcporter --config "$TALLY_MCP_CONFIG" list tally --brief --no-oauth
   ```

2. Pick the exact tool name from that output, then inspect only its schema.
   For large tools (`create_blocks`, `configure_blocks`, `update_settings`), use
   [filtered discovery](references/mcporter-discovery.md) to read only the needed
   block types, operations, or settings. For small tools:

   ```bash
   mcporter --config "$TALLY_MCP_CONFIG" list tally.TOOL_NAME --schema --no-oauth
   ```

3. Call the tool with arguments matching its current schema:

   ```bash
   mcporter --config "$TALLY_MCP_CONFIG" call tally.TOOL_NAME --args '{"ARGUMENT":"VALUE"}' --output json --no-oauth
   ```

   `TOOL_NAME`, `ARGUMENT`, and `VALUE` are placeholders. Do not guess names or
   reuse arguments from a different tool. For large payloads, use a
   local JSON file and shell-quote its contents: `--args "$(cat /absolute/path/arguments.json)"`.

If authentication is missing, follow [connection.md](references/connection.md).
Do not dump all schemas or load all reference pages. MCP tools may themselves
return usage instructions; follow those for the chosen operation.

## Forms

- Before `create_new_form`, `load_form`, or any operation on the working form,
  read [mcporter-daemon.md](references/mcporter-daemon.md) and acquire its session
  lock. The keep-alive connection is shared by agents and holds one working form.
  Hold the lock through editing, saving, and verification; never interleave forms.
- Start with `create_new_form` or `load_form`. Edit through the returned ledger
  and targeted MCP tools. These changes remain in memory until `save_form`.
- Create the form the user requested. Use `DRAFT` unless publishing was requested;
  preserve an existing form's status unless the task changes it. If a tool cannot
  express the requested status, explain that before writing.
- Always pass `save_form.status` explicitly: its current default is `PUBLISHED`.
  After the first save, always pass the saved `formId` on subsequent saves.
- Before editing, load the target form and retain its existing IDs. Use UUIDs from
  the returned ledger; MCP creation tools generate new IDs.
- `create_blocks` currently makes questions required. Use `configure_blocks`
  to make requested fields optional, then verify the ledger.
- `create_blocks` may strip the final parenthesized phrase from a question title.
  If the intended title ends with `(...)`, restore the full title using
  `update_text` after creation. Verify it after saving and reloading the form.
- Before saving, call `list_blocks` and compare the working content with the
  request. After saving, reload the saved form and check its content; verify
  status through saved metadata or `list_forms`. Do not reload during unsaved
  editing, because loading replaces the working form. Report its ID/link and
  whether it is draft or published. If a save times out, inspect stored state
  before retrying; do not blindly create a duplicate.

## Responses

Inspect `fetch_submissions` for response retrieval or `fetch_insights` for
aggregate analytics. Filter to the requested form, period, and completion state;
follow pagination when the task needs the complete set. Report the scope and
number of responses covered. Keep answers out of the skill and committed fixtures.

## Further details

Tool descriptions and live schemas define the supported operations and arguments.
Read them on demand through MCPorter. If they leave a product question unanswered,
inspect and use Tally's `search_documentation` tool. Report missing capabilities;
do not invent tools or silently switch to another interface.
