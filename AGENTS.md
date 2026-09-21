# Skill Authoring Rules

Skills in this repository should follow the Agent Skills spec so they work across Claude, Codex, OpenCode, and other compatible clients.

Maintainer-approved user-only skills are one explicit exception. They may use `disable-model-invocation: true` in `SKILL.md` for Claude Code and Pi, plus a minimal `agents/openai.yaml` with `policy.allow_implicit_invocation: false` for Codex. Their descriptions must also forbid automatic use as a fallback for clients that ignore these extensions.

Source of truth:

- https://agentskills.io/llms.txt

Before creating or editing a skill here, fetch the current docs from that index and read them.

## Spec compliance

- the specification page must be read before authoring or changing a skill
- do not copy spec details into this file; use the upstream docs as the canonical reference
- keep skills portable and avoid machine-specific assumptions

## Privacy (hard rule)

This repository is public. Do not commit:

- internal project, product, client, or organization names
- ticket IDs, codenames, or internal URLs
- credentials, tokens, API keys, or auth material
- absolute paths from any author's machine
- personal data or context that is not meant to be public

Audit every new or modified skill for leaks before commit. If unsure, do not commit.

## Conventions

- one skill per folder, kebab-case name
- keep `description` as short as possible while letting the agent select the
  right skill: purpose and essential selection boundaries only; descriptions
  consume context before loading, so put workflow steps, implementation details,
  examples, and extended capability lists in the body or references
- relative paths within a skill, never absolute
- keep skill content independent of where it is installed: no workspace names,
  checkout paths, local/global installation claims, or personal setup instructions
  in `SKILL.md`, references, or bundled helpers; keep deployment details in the
  consuming environment's setup docs and resolve bundled resources relative to
  the skill itself
- English for skill content unless the skill is explicitly about a non-English context
- prefer minimal changes when updating an existing skill
- do not create or regenerate `agents/` UI metadata folders, including `agents/openai.yaml`, unless explicitly requested by the maintainer
- new coding-focused skills should use `coding-<verb>-<object>` names; keep already-published names stable unless doing an explicit compatibility migration
