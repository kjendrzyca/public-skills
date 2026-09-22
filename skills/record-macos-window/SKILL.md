---
name: record-macos-window
description: Record a single macOS window as silent video with a verified 60 fps export. Use only when explicitly invoked by name.
disable-model-invocation: true
---

# Record macOS Window

Record one macOS window at native pixel density, then create a delivery copy with an exact 60 fps timeline. Treat capture, normalization, and visual QA as separate gates.

## Requirements

- macOS 15 or newer.
- Xcode Command Line Tools with `xcrun` and `swiftc`.
- `ffmpeg` and `ffprobe` on `PATH`.
- Screen Recording permission for the terminal or agent host that runs the recorder.
- A browser or app automation tool when the recording needs scripted actions.

Resolve this skill's installed directory from the active skill catalog, but stay in the user's workspace. Set `skill_dir` to that resolved directory and keep all source, delivery, and QA artifacts under a workspace-owned ignored directory such as `.agent-data/record-macos-window/<take>` or an OS temporary directory. Never write generated artifacts into the installed skill.

The examples use these placeholders:

```bash
skill_dir="RESOLVED_SKILL_DIRECTORY"
take_dir=".agent-data/record-macos-window/demo"
mkdir -p "$take_dir"
```

Use `--help` on any bundled script before changing its defaults.

## Workflow

### 1. Define the take

Write the short action sequence before recording. Include:

- the exact window and owner application;
- the clean starting state;
- each click, key press, scroll, or wait;
- the final state that must remain visible;
- the raw source path, delivery path, and QA artifact directory.

Use one continuous take when possible. Rehearse once before the final take so browser element references, menus, and timing are known.

### 2. Prepare the window

1. Set the window size and zoom before capture. Do not resize it during a take.
2. Close unrelated tabs, private data, notifications, password managers, and overlays. Close or rename sensitive windows before any filtered listing.
3. Reset the app to the intended start state.
4. For browser automation, take a fresh accessibility snapshot and confirm every action target.
5. Leave about one second of stable footage before the first action and after the final state. Trim those handles during normalization.

List only windows that match a narrow title filter before choosing the target. A title filter is required because listing prints matching titles; add an owner filter only to narrow those title matches further:

```bash
"$skill_dir/scripts/record-window" \
  --list-windows \
  --window-title "Demo" \
  --owner-name "Browser"
```

Unfiltered and owner-only listing are refused because they may expose unrelated private titles from one application. Treat even title-filtered list output as transient sensitive data: use it only to select the window ID, then discard it. Never paste it into chat, reports, commits, or published artifacts.

Use `--window-id` from the filtered list for an exact target. A title and owner query must resolve to one unique visible window; the recorder refuses ambiguous matches.

### 3. Coordinate capture and actions

Start the recorder in a long-running terminal session with a short initial yield:

```bash
"$skill_dir/scripts/record-window" \
  --window-id 1234 \
  --duration 30 \
  --output "$take_dir/demo-source.mp4"
```

Wait for the JSON `READY` event before performing actions. Then:

1. Keep the opening handle stable.
2. Execute only the rehearsed browser or app actions.
3. Pause long enough for each animation and async state to settle.
4. Hold the final state for the closing handle.
5. Let the recorder finish. Do not kill it after the last action because an interrupted MP4 may not finalize.

The cursor is visible by default because it explains most UI actions. Pass `--hide-cursor` only when the take should focus on animation without pointer movement. This v1 workflow records silent video only.

If ScreenCaptureKit cannot list windows, grant Screen Recording access in macOS settings, restart the terminal or agent host, and rerun the list command.

Do not take browser screenshots or run exploratory browser inspection while capture is active. Those actions can steal focus, add visual noise, or change the page. Use the rehearsed interaction sequence and take any diagnostic screenshots before or after the take.

### 4. Normalize to exact constant 60 fps

ScreenCaptureKit requests up to 60 fps. Its raw MP4 can still use variable frame timing because unchanged content does not require a new frame. Normalize every delivery copy:

```bash
python3 "$skill_dir/scripts/normalize-video.py" \
  --input "$take_dir/demo-source.mp4" \
  --output "$take_dir/demo-60fps.mp4" \
  --trim-start 1.0 \
  --trim-end 18.5
```

The script applies ffmpeg's `fps=60` filter, CFR output mode, a 60 fps stream rate, and a track timescale that represents every frame interval exactly. It encodes silent H.264 with `yuv420p`, writes to a temporary sibling file, verifies that file, and only then replaces the requested output.

Use strict pixel crop and scale flags when the delivery must exclude browser chrome or match a fixed canvas:

```bash
python3 "$skill_dir/scripts/normalize-video.py" \
  --input "$take_dir/demo-source.mp4" \
  --output "$take_dir/demo-60fps.mp4" \
  --crop 2880:1800:0:160 \
  --scale 1440:900 \
  --trim-start 1.0 \
  --trim-end 18.5
```

Determine crop values from inspected source frames. The normalizer rejects crops outside the source frame before encoding. Do not guess or stretch the UI to force an aspect ratio.

Normalization creates a 60 fps timeline; it cannot recover motion that the source never captured. ffmpeg may repeat a source frame across a longer source interval. Judge motion with the focused QA strips, not metadata alone.

### 5. Verify media timing

The normalizer runs verification automatically. Run it again when receiving or editing a delivery file:

```bash
python3 "$skill_dir/scripts/verify-video.py" \
  --input "$take_dir/demo-60fps.mp4" \
  --expected-fps 60 \
  --expected-width 1440 \
  --expected-height 900
```

A passing result requires:

- declared and average frame rates of exactly `60/1`;
- a time base that can represent `1/60` exactly;
- zero missing, repeated, or irregular presentation timestamps;
- frame count and stream duration consistent with that timeline;
- a clean full-stream ffmpeg decode with no corrupt frames;
- any requested width and height.

Do not call a video constant 60 fps when this check fails.

If verification reports a decode error, keep the source and diagnostics. Check whether the raw source also has decoding errors:

```bash
ffmpeg -v error -xerror -i "$take_dir/demo-source.mp4" -map 0:v:0 -f null -
```

A nonzero exit or error output means decoding failed. Do not use the CFR verifier to diagnose raw-source corruption: variable frame timing alone is normal. Report the failure and propose a new export if the source decodes cleanly, or a new recording if the source is damaged. Do not silently drop damaged frames or claim that re-encoding recovers missing content; salvage requires the user's approval.

### 6. Generate and inspect visual QA

Create one broad contact sheet and focused motion strips around important actions:

```bash
python3 "$skill_dir/scripts/make-video-qa.py" \
  --input "$take_dir/demo-60fps.mp4" \
  --output-dir "$take_dir/qa" \
  --focus-time 4.25 \
  --focus-time 9.80
```

When a small counter or control remains unreadable, regenerate QA with a strict known pixel crop. The crop applies before scale to both the broad contact sheet and motion strips:

```bash
python3 "$skill_dir/scripts/make-video-qa.py" \
  --input "$take_dir/demo-60fps.mp4" \
  --output-dir "$take_dir/cropped-qa" \
  --focus-time 9.80 \
  --crop 600:240:760:600 \
  --tile-width 600
```

Derive crop coordinates from inspected frames; never guess them automatically. Invalid syntax and out-of-frame bounds must fail rather than fall back to a full-frame image.

Read [references/visual-qa.md](references/visual-qa.md), then inspect every generated image with the agent's image-viewing tool. Add another `--focus-time` for any transition that remains unclear. Do not treat contact-sheet generation as visual review.

Re-record when the action, state, cursor, window, or source motion is wrong. Re-normalize when only trim, crop, scale, encoding, or frame timing is wrong.

### 7. Clean up

Keep the raw capture and QA artifacts until the user accepts the normalized delivery. Then report every exact intermediate path proposed for removal, excluding the final delivery, and use the host agent's normal approval-gated exact-path cleanup workflow. Do not infer targets from globs and do not use a generic recursive deletion helper from this skill.

Report the final file path, verification result, visual QA result, and every removed intermediate.

## Guardrails

- Record only the window and actions in scope. A recording request does not authorize unrelated browsing or data access.
- Never expose secrets, private notifications, unrelated tabs, or personal data in the source or QA images.
- Do not overwrite source or delivery files unless the user asked for replacement and you pass `--overwrite`.
- Do not use a screen-wide recorder when a single-window capture meets the request.
- Do not delete raw footage before the delivery copy passes both timing and visual checks.
- Do not claim that CFR normalization proves 60 unique captured images per second.
