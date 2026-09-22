# Visual QA Checklist

Inspect the contact sheet first, then each focused motion strip. Record observed facts before conclusions.

## Contact sheet

- Confirm that every tile shows the intended app, browser, account, and page.
- Check the first and last useful states. Trim dead time, setup actions, and accidental pointer placement.
- Check window geometry, crop, scale, aspect ratio, text sharpness, color, and contrast.
- Look for permission prompts, notifications, browser chrome, unrelated tabs, dev overlays, loading flashes, blank frames, and private data.
- Confirm that popovers, menus, tooltips, and fixed bars remain inside the frame.
- Check that scroll and layout positions change only when the action sequence calls for them.

## Focused motion strips

- Read tiles from left to right and top to bottom.
- Confirm the expected state order around each click, key press, counter change, list move, menu, or route transition.
- Look for jumps, teleports, duplicated-looking pauses, missing intermediate states, stale frames, tearing, flicker, and one-frame flashes.
- Check animated numbers and text at full image detail. Make sure glyphs do not overlap, clip, blur, or roll in the wrong direction.
- Check that cursor motion, when included, supports the action and does not cover the result.

Exact 60 fps timestamps do not prove that all frames contain unique source images. Repeated-looking tiles can reveal a capture gap or an intentionally static interval. Compare them with the expected UI behavior before judging the take.

## Disposition

- Re-record when the source contains the wrong action, state, window, cursor behavior, notification, private data, or missing motion.
- Re-normalize when the source is sound but trim, crop, scale, encoding, or output timing is wrong.
- Accept only when timing verification passes and every important transition has direct visual evidence.
