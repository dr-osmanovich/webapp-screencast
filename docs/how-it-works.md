# How webapp-screencast works

Three stages, each a plain file you can inspect:

```
scenario.py ──► webapp-screencast record ──► footage/take.mp4 + events.json
plan.py     ──► webapp-screencast compose ─► composition/ (index.html, studio.js, footage/)
                webapp-screencast render ──► video.mp4   (HyperFrames: check → 60 fps H.264)
```

## 1. Capture

`record` launches headless Chromium through Playwright with hardware-GPU flags and runs your
scenario: `take.click`, `take.type`, `take.move`, `take.scroll_to`, `take.mark`, `take.box`.
Frames come from the Chrome DevTools Protocol (`Page.startScreencast`), so:

- **no macOS Screen Recording permission** is needed, and it works on a CI box;
- frames arrive only when the page repaints; each is held for its real duration and the result is
  assembled into constant 60 fps (`ffmpeg concat` + `fps=60`, cut with `-t`);
- the footage is at device scale factor 2 by default (3840×2160 for a 1920×1080 viewport), so a 2×
  zoom still shows native pixels;
- the pointer is **not** in the footage. Every move, press, release, key and scroll is logged with
  the same epoch clock the frames carry (`events.json`), and the pointer is drawn again in post.

Why re-render the pointer instead of recording it: a recorded cursor is 1 px thin, jitters with
the hand and cannot be enlarged or smoothed afterwards. Logging it makes it a clean, oversized arrow
with press feedback and a click ring, exactly like dedicated screen-recording apps do.

## 2. Compose

`compose` reads `events.json`, hands marks and element boxes to your `plan.py`, and writes a
HyperFrames project. The runtime (`studio.js`) is deliberately small:

- **Stage**: wallpaper layer, the footage in a rounded window (5 % side padding, 28 px radius,
  1 px inset frame, two-layer shadow). Everything lives in one `#sc-world` element.
- **Camera**: a plan of segments `{from, zoom, focus}`. The focus point and the zoom each run
  through a *critically damped spring* (ω = 5.2 and 4.2 rad/s) integrated at 240 Hz and sampled
  at 60 fps, so every move eases in and out without overshoot and without authoring tweens.
  The world is clamped so the canvas is always covered.
- **Cursor**: linear replay of the logged path (it is already eased), 56 px arrow, press scale
  and an expanding ring on each `down` event.
- **Subtitles, title cards, callouts, halos, SFX, music** from the plan.

All of it is a pure function of time read back by one proxy tween on the paused GSAP timeline,
which is what HyperFrames needs for deterministic, seek-safe rendering.

## 3. Render

`render` runs `hyperframes check` (lint, layout, WCAG contrast) and then `hyperframes render`
at 60 fps, `--quality delivery`, PNG frame extraction for the footage. `poster` bakes a chosen
frame as frame 0 so thumbnails never land on a crossfade.

## Timing model

Plan times are **footage seconds** (what `take.mark` recorded). The composer maps them to the
composition with `video_start + (t - media_start)`; title cards shift everything else.
Subtitles are checked against a reading floor of 0.3 s per word.
