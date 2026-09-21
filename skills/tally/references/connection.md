# Connection

Requires MCPorter and network access; filtered discovery also uses `jq`.
The commands below were checked with MCPorter 0.13.13. If MCPorter is missing,
install it with the environment's package manager; for npm, use
`npm install -g mcporter@0.13.13`.

Resolve the bundled `mcporter.json` relative to `SKILL.md` and set
`TALLY_MCP_CONFIG` to its absolute path in each shell invocation, as described in
[the skill](../SKILL.md). The config points to `https://api.tally.so/mcp` and uses
OAuth with a keep-alive connection.

```bash
mcporter --config "$TALLY_MCP_CONFIG" auth tally
mcporter --config "$TALLY_MCP_CONFIG" list tally --status --exit-code --no-oauth
```

The first command opens a browser for the user to log in and authorize Tally.
The second checks access without starting another login. Agents using the same
config and OS account share MCPorter credentials and the working session;
follow [session coordination](mcporter-daemon.md) before loading or editing forms.

MCPorter stores OAuth tokens in its user data directory, by default
`~/.mcporter/credentials.json`, or its configured XDG location. Do not print or
copy credentials into the skill or a repository.

For an auth error, ask the user to finish login. For permission errors or missing
capabilities, report the exact failure. Do not reset working credentials, switch
accounts, or introduce an API key as an automatic fallback.

Sources, checked 2026-09-21:

- [MCPorter configuration](https://github.com/openclaw/mcporter/blob/main/docs/config.md)
- [Tally MCP](https://developers.tally.so/api-reference/mcp)
