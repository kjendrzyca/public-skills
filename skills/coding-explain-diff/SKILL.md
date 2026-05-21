---
name: coding-explain-diff
description: Explain a GitHub pull request from a PR URL by creating an isolated checkout when needed, organizing changed files into logical groups, and writing a structured Markdown report with per-group explanations, important snippets, and GitHub PR diff links. Use when asked to explain a PR, summarize what changed in a PR, or group a diff into reviewable sections.
license: MIT
compatibility: Requires git, network access to GitHub, and GitHub CLI (`gh`) authenticated for PR metadata, cloning, and diffs.
---

# Coding Explain Diff

Create a Markdown explanation of a GitHub pull request from a PR URL. The output should help a human reviewer understand the diff quickly: group related changes by intent, explain each group with evidence from the diff, include important snippets for significant changes, and link back to the PR Files view.

## Core Rules

- Accept a GitHub PR URL as the primary input. Do not require the user to manually checkout the repository.
- Use `gh` as the default source for PR metadata and diffs.
- Use an existing local checkout only when it already points at the PR head. Otherwise create an isolated scratch checkout in a temp directory and analyze the PR there.
- Keep the user's working tree read-only by default. Do not checkout branches, fetch refs, edit source files, post GitHub comments, push, or change the user's git state unless the user explicitly approves that action.
- It is OK to clone and checkout the PR inside the scratch checkout because it is disposable agent workspace.
- Write one Markdown artifact under the analysis checkout's `.agent-data/coding-explain-diff/` using a collision-resistant compact timestamp filename.
- Prefer GitHub PR diff links for human-facing file references. Keep local repo-relative paths as fallback/context.
- Leave scratch checkouts in place after the run so report references remain inspectable. The user or OS can clean temp directories later.
- Do not post the report to GitHub in v1.
- Let agent judgment drive grouping and explanation. Do not reduce grouping to path sorting or a fixed algorithm.

## Workflow

1. Confirm `gh` is available and authenticated enough to read the PR and clone the repository. If not, ask the user to authenticate or provide another approved data source.
2. Parse the PR URL into owner, repository, and PR number.
3. Capture PR metadata: number, title, URL, author, base branch, head branch, changed file count, additions, deletions, description, commits, and the PR head commit SHA when available.
4. Choose the analysis checkout.
   - Example current repo command: `gh repo view --json nameWithOwner --jq .nameWithOwner`
   - Use the current checkout only if it is the same repository, `HEAD` equals the PR head commit, and local uncommitted changes will not distort the analysis.
   - If the current directory is a matching repository but not at the PR head, do not mutate it. Create a scratch checkout instead.
   - If the current directory is unrelated or not a git checkout, create a scratch checkout.
5. Create a scratch checkout when needed.
   - Use a temp root such as `${TMPDIR:-/tmp}/coding-explain-diff/`.
   - Use a collision-resistant directory name such as `owner-repo-pr-123-YYYYMMDDTHHMMSS`.
   - Clone with `gh repo clone OWNER/REPO <checkout-dir>`.
   - In the scratch checkout, run `gh pr checkout 123`.
6. Collect changed files with additions/deletions and the patch/diff from the analysis checkout.
7. Build GitHub PR Files links for changed files and important line references.
   - File diff URL shape: `https://github.com/OWNER/REPO/pull/NUMBER/files#diff-DIFF_ID`.
   - Line URL shape when known: `https://github.com/OWNER/REPO/pull/NUMBER/files#diff-DIFF_IDR42` for the right side of the diff, or `...L42` for the left side.
   - GitHub's `DIFF_ID` is normally `sha256(repo-relative-path)` as lowercase hex. For renamed files, use the current filename first; if uncertain, link to the file diff without a line anchor or to the PR Files tab.
   - Do not invent precise line anchors. If unsure, link to the file diff header and show the local path separately.
8. Read enough relevant local files from the analysis checkout to understand changed code in context, using repo-relative paths.
9. Build logical change groups by intent.
   - Prefer concept and purpose over alphabetical order.
   - Merge files that support the same behavior change.
   - Split one file across groups when separate hunks serve different purposes.
   - For each group, plan evidence for the important files and hunks. Do not list files in a group and then only show evidence for one of them unless the omitted changes are trivial or repetitive.
   - Consider every meaningful changed file internally, but do not include a public coverage checklist.
10. Write the report from `references/report-template.md`.
11. Reply with the report path, the analysis checkout path when a scratch checkout was created, and a brief 3-5 bullet overview. Do not paste the full report unless the user asks.

## Output Location

Create the directory inside the analysis checkout if needed:

```bash
mkdir -p .agent-data/coding-explain-diff
```

Use this filename shape:

```text
.agent-data/coding-explain-diff/YYYY-MM-DDTHHMMSS-pr-123.md
```

Use a compact ISO-like timestamp without colons so filenames are portable, for example `2026-05-13T143022-pr-123.md`. When analyzing from a scratch checkout, this path is relative to that scratch checkout.

## Report Guidance

Read `references/report-template.md` before writing the report.

Use Markdown links to the PR Files view for primary references, with link text such as `src/server/router.ts:42`. If a line number is uncertain, link to the file diff header and use link text like `src/server/router.ts`. Keep local paths in the report so the scratch checkout remains useful for follow-up inspection.

For snippets:

- Use `Important snippets` as an evidence walkthrough, not as a single representative code block.
- Interleave short explanations with snippets when that makes the group easier to understand.
- Bias strongly toward covering every meaningful file in the group. If a file is listed in the group and has a significant change, include a snippet or a nearby explanation for it.
- It is acceptable to omit a snippet for a trivial, mechanical, or repetitive file change, but still mention what changed if the file appears in the group.
- Choose snippets that are complete enough to explain the change. Do not optimize for the shortest possible fragment; optimize for whether the snippet does its explanatory job.
- Do not paste an arbitrary prefix of a function, query, type, or block. A snippet must be semantically complete or explicitly elided.
- If code is omitted from the middle of a snippet, add language-appropriate elision comments such as `// ... unchanged validation ...`, `/* ... omitted setup ... */`, or `-- ... omitted metadata columns ...`.
- For long SQL strings, query builders, or generated payloads, prefer a compact skeleton that preserves the important clauses, filters, joins, ordering, and returned fields over a mechanically copied partial hunk.
- Include the closing part of a block when it matters to understanding control flow, return shape, query semantics, or error handling. If the closing part does not matter, mark the remainder as omitted.
- Prefer changed lines plus enough surrounding context to make the fragment understandable.
- Use pseudocode instead of raw code when full code is noisy or sensitive.
- Do not paste large hunks or full files.

If you notice an obvious bug, regression risk, or missing test while explaining the PR, add a clearly separate `## Potential review findings` section. Keep it brief and evidence-based. Do not turn the task into a full defect review unless the user asks.

## Failure Modes

- If `gh` is unavailable or unauthenticated, stop and ask the user instead of silently switching to an unreliable path.
- If scratch checkout creation fails, show the failing command and ask the user whether to retry, use an existing checkout, or provide the diff another way.
- If a diff is too large for one pass, analyze it in chunks and synthesize groups at the end. Do not skip grouping just because the PR is large.
