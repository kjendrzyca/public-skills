# Filtered tool discovery

Source: [MCPorter CLI reference](https://github.com/openclaw/mcporter/blob/main/docs/cli-reference.md)
Checked: 2026-09-21 against MCPorter 0.13.13 and the live Tally schemas.

Set `TALLY_MCP_CONFIG` as described in [the skill](../SKILL.md). MCPorter
fetches the schema; `jq` keeps unrelated branches out of agent context. These filters only inspect metadata; they do not call a form tool.

For a question title and short-text answer, keep those two block variants:

```bash
mcporter --config "$TALLY_MCP_CONFIG" list tally.create_blocks --json --no-oauth |
  jq '.tools[0] | {name, inputSchema} |
    .inputSchema.properties.groups.items.properties.blocks.items.anyOf |=
    map(select(.properties.type.enum[] | IN("TITLE", "INPUT_TEXT")))'
```

Replace the type names with those needed for the task. The outer schema remains
intact, including required fields, group limits, and insertion-point rules.
`create_blocks` defaults questions to required; make optional fields explicit
through `configure_blocks`. Read its description for unfamiliar placement or
grouping behavior.

Discover configuration operations without their full schemas:

```bash
mcporter --config "$TALLY_MCP_CONFIG" list tally.configure_blocks --json --no-oauth |
  jq -r '.tools[0].inputSchema.properties.updates.items.anyOf[].properties.operation.enum[]'
```

Then inspect the chosen operation, for example input settings:

```bash
mcporter --config "$TALLY_MCP_CONFIG" list tally.configure_blocks --json --no-oauth |
  jq '.tools[0] | {name, description, inputSchema} |
    .inputSchema.properties.updates.items.anyOf |=
    map(select(.properties.operation.enum[] == "input_settings"))'
```

For a settings change, first list property names, then select the needed properties:

```bash
mcporter --config "$TALLY_MCP_CONFIG" list tally.update_settings --json --no-oauth |
  jq '.tools[0].inputSchema.properties | keys'

mcporter --config "$TALLY_MCP_CONFIG" list tally.update_settings --json --no-oauth |
  jq '.tools[0] | {name, description, inputSchema} |
    .inputSchema.properties |= with_entries(select(.key == "language" or .key == "hasProgressBar"))'
```

To read a tool's full instructions separately, use the same `list ... --json`
command with `jq -r '.tools[0].description'`. If a filter returns an empty branch
or required properties are missing, inspect the live schema and adjust the filter;
do not call the tool based on incomplete discovery.
