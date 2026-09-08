# Changelog

## 2026-09-08

### Add focused sketches to coding-explain-diff

- Change groups can use pseudocode, call trees, component trees, or shallow file trees to explain the relevant logic, runtime order, UI state ownership, or file responsibilities.
- Small flow changes prefer a schematic diff; larger changes keep separate Before/After views when they make the sequence clearer.
- Synthesized views carry a Schematic or Pseudocode label and links to the supporting PR changes. Sketches preserve evidence for meaningful files and omit details already clear from prose, snippets, or the overall architecture.

## 2026-08-28

### Add bird's-eye architecture diagrams to coding-explain-diff

- PR explanations now include a simple, top-down ASCII architecture diagram when the runtime flow crosses several components or system boundaries.
- Diagrams start from the real caller or entry point, use names from the diff, and show the main handoffs, return values, and decision branches.
- Small local changes omit the architecture diagram, and before/after diagrams stay optional so reports do not repeat the same flow twice.

## 2026-07-23

### Redesign coding-audit-assumptions

- The skill is now human-invoked only: it must never trigger automatically or run as an internal step of planning, review, or remediation.
- Its proposals go to the human for assessment, with the agent's own critical evaluation attached; nothing is implemented without explicit approval.
- The goal changed from "make the failure mode impossible" to out-of-the-box thinking that hits the root of the problem and simplifies or dissolves it, usually with less work and less code.
