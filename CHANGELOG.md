# Changelog

## 2026-07-23

### Redesign coding-audit-assumptions

- The skill is now human-invoked only: it must never trigger automatically or run as an internal step of planning, review, or remediation.
- Its proposals go to the human for assessment, with the agent's own critical evaluation attached; nothing is implemented without explicit approval.
- The goal changed from "make the failure mode impossible" to out-of-the-box thinking that hits the root of the problem and simplifies or dissolves it, usually with less work and less code.
