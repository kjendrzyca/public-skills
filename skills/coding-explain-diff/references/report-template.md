# Diff Explainer Report Template

Use this template for every report. Adapt wording to the PR, but keep the same section order.

````markdown
# PR #[number]: [title]

## Metadata

- URL: [PR URL]
- Author: [author]
- Base -> head: `[base]` -> `[head]`
- Changed files: [count]
- Diff stats: +[additions] / -[deletions]
- Analysis source: [current checkout at PR head | scratch checkout]
- PR files: [Files view]([PR URL]/files)
- Report generated: [timestamp]

## Overall summary

[One or two short paragraphs explaining what the PR does and the main areas changed. Define the core entities and any project-specific terms before using them to explain the flow. Stay neutral and explanatory. Do not lead with review judgments.]

## System flow: before and after

[Include this section only when the PR changes architecture, data flow, system boundaries, or a workflow that spans several components. Remove it for small, local changes. Use plain labels, and define any necessary project-specific terms in `Overall summary` before they appear here.]

```text
Before
  [current flow on the base branch]

After
  [flow at the PR head]
```

- Added: [new components, stored state, or behavior]
- Changed: [existing flow or responsibility that works differently]
- Unchanged: [important existing behavior or explicit non-goals]

## Change groups

### 1. [Group title]

Files: [`[path:line]`]([GitHub PR diff link]), [`[path]`]([GitHub PR file diff link])
Stats: [n files], +[additions], -[deletions]
Why grouped: [short phrase explaining why these edits belong together]

<details>
<summary>Read explanation</summary>

#### Explanation

[Explain the change as a reviewer would want to understand it. Cover what changed, where it fits in the flow, and why it matters.]

#### Important snippets

[Explain the first significant file or hunk in this group. Prefer one or two sentences that connect the snippet to the group intent.]

[`[path:line]`]([GitHub PR diff line link])

```[language]
[snippet that is complete enough to explain this part of the change]
```

[If the changed block is long, show a complete focused skeleton instead of an arbitrary prefix. Mark intentional omissions inside the snippet with comments.]

```[language]
[start of relevant block]
// ... omitted unchanged or less relevant middle ...
[changed lines that explain the behavior]
// ... omitted unchanged or less relevant middle ...
[closing lines when they clarify control flow, return shape, or query semantics]
```

[Explain the next significant file or hunk. Include additional snippets for meaningful files in the group; do not rely on one representative snippet when multiple files carry important behavior.]

[`[path:line]`]([GitHub PR diff line link])

```[language]
[another important snippet]
```

[If a listed file is trivial or repetitive, mention that briefly instead of adding a noisy snippet.]

#### PR diff links

- [`[path:line]`]([GitHub PR diff line link]) - [what to look at]
- [`[path]`]([GitHub PR file diff link]) - [what to look at]

#### Local paths

- `[path:line]`
- `[path]`

</details>

### 2. [Group title]

Files: [`[path:line]`]([GitHub PR diff link])
Stats: [n files], +[additions], -[deletions]
Why grouped: [short phrase]

<details>
<summary>Read explanation</summary>

#### Explanation

[Explanation]

#### Important snippets

[Explain the relevant file or hunk. Add more snippet blocks when the group spans multiple meaningful changes.]

[`[path:line]`]([GitHub PR diff line link])

```[language]
[snippet]
```

#### PR diff links

- [`[path:line]`]([GitHub PR diff line link]) - [what to look at]

#### Local paths

- `[path:line]`

</details>

## Potential review findings

[Optional. Include this section only if there are obvious, evidence-backed risks noticed during explanation. Keep it separate from the neutral explanation.]

- [Severity if useful]: [finding with local reference]
````

## Formatting Rules

- Keep `<details>` blocks closed by default. Do not add the `open` attribute.
- Include `System flow: before and after` only for PRs that change architecture, data flow, system boundaries, or a multi-component workflow. Omit it for small, local changes.
- Keep the before/after diagram accurate to the base branch and PR head, scannable in under 60 seconds, and free of terms that were not defined earlier.
- Use numbered group headings in review order, not alphabetical file order.
- Keep group titles concrete: name the behavior or code area, not just the filename.
- Keep `Why grouped` to one short phrase.
- Use `Important snippets` as an interleaved evidence walkthrough. A group may have multiple snippets.
- Bias strongly toward representing every meaningful file in the group with either a snippet or a short explanation.
- Snippets should be long enough to do their explanatory job, not necessarily the shortest possible fragment.
- Never paste an arbitrary prefix of a function, query, type, or block. Snippets must be semantically complete or explicitly elided with language-appropriate comments.
- For long SQL strings or query builders, prefer a compact skeleton preserving important clauses, filters, joins, ordering, and returned fields over a mechanically copied partial hunk.
- Include closing lines when they clarify control flow, return shape, query semantics, or error handling. Otherwise mark the remainder as omitted.
- Prefer GitHub PR Files links for clickable references. Use local repo-relative paths as link text and as fallback context.
- Link to a file diff header when a precise line anchor is uncertain.
- Do not add a changed-file coverage checklist to the report.
- Do not include raw secrets, tokens, or large copied payloads from the diff.
