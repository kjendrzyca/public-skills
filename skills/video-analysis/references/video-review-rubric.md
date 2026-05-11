# Video Review Rubric

Use this rubric when reviewing UX, onboarding, QA, or bug-report recordings.

## What To Look For

- User hesitation: pauses, repeated clicks, or spoken uncertainty.
- State mismatch: UI says one state while the product or browser has moved to another.
- Hidden dependency: progress depends on a popup, tab, refresh, or manual reopen that is not obvious.
- Copy mismatch: labels describe implementation details instead of user goals.
- Missing recovery: no retry, refresh, fallback, or clear next action after a failure.
- Latency ambiguity: loading state lacks an expected duration or progress transition.
- Success ambiguity: the user cannot tell whether an action succeeded.

## Evidence Quality

High-confidence evidence combines at least two sources:

- Transcript quote.
- Frame or contact-sheet visual state.
- Repeated visible state across multiple frames.
- Code path that plausibly explains the observed behavior.

Medium-confidence evidence has one source plus a plausible interpretation. Label it as a hypothesis.

Low-confidence evidence is a hunch. Do not present it as a finding unless the user explicitly asks for brainstormed possibilities.

## Practical Review Flow

1. Skim `metadata.md` for duration and stream details.
2. Read `transcript.md` once for user intent and confusion points.
3. Open `contact-sheet.jpg` to map screen states to timestamps.
4. Generate or inspect focused windows around confusing timestamps.
5. Write timeline first, findings second, likely causes third.
