# Skill Authoring Rules

All skills in this repository must be compatible with the Agent Skills spec so they work across Claude, Codex, OpenCode, and other compatible clients.

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
- relative paths within a skill, never absolute
- English for skill content unless the skill is explicitly about a non-English context
- prefer minimal changes when updating an existing skill
- do not create or regenerate `agents/` UI metadata folders, including `agents/openai.yaml`, unless explicitly requested by the maintainer
- new coding-focused skills should use `coding-<verb>-<object>` names; keep already-published names stable unless doing an explicit compatibility migration
