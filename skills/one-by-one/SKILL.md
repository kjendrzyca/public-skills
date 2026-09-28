---
name: one-by-one
description: Ask the user a list of questions one at a time, letting each answer reshape the rest. Use before asking three or more open questions or decisions at once, or when the user asks to go one by one.
license: MIT
---

# One by one

Keep the questions in a queue and ask one per turn. Wait for the answer before asking the next.

- Ask through the client's built-in question tool when it has one (for example `AskUserQuestion` in Claude Code); otherwise ask in plain chat.
- Give each question the short context needed to answer it, the options, and mark your recommended option.
- After each answer, update the queue: drop questions the answer made moot and add the ones it opened. Show roughly how many remain (for example "question 2, about 4 left").
- When the queue is empty, summarize the decisions.
