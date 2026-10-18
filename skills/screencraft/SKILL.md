---
name: screencraft
description: Make a smooth, Screen Studio-style demo video of a web app from real footage — scripted headless 60 fps capture, spring auto-zoom camera, re-rendered cursor, padded stage, subtitles and callouts — with the screencraft CLI. Use when asked to record a product demo / walkthrough / launch video / screen recording of a web app, to "make it look like Screen Studio", or when /brag (or any launch-video skill) should use real app footage instead of screenshots.
---

# screencraft

You script the take, screencraft records it and edits it. Output: `OUT/<name>.mp4` (1920×1080, 60 fps)
plus a poster `.jpg`. Everything is a file you write (`scenario.py`, `plan.py`) and one CLI.
Always call the CLI with `--json` (before the subcommand): stdout is one JSON object
(`ok`, `error`, paths, durations, warnings); progress goes to stderr. Exit 0 ok, 1 step failed, 2 bad input.

API and plan keys: [reference.md](reference.md). Read it before writing scenario.py / plan.py.

## 0. Setup (once per machine)

```bash
screencraft --json doctor
```
If `screencraft` is missing: `pip install git+https://github.com/dr-osmanovich/screencraft.git`
(use the project's venv if it has one), then `python -m playwright install chromium`.
`doctor` lists each failing check with its `fix`. Node 22+ and ffmpeg are required for rendering.

## 1. Understand the app (before any recording)

- Find how it runs locally (README, package.json scripts, Makefile, docker-compose) and its URL.
  A plain static folder can be served by screencraft itself (`make --serve DIR`).
- Find **demo/seed data and test accounts** in the repo (fixtures, seed scripts, `.env.example`).
  Never record production, real customer or patient data, or real credentials. If no safe demo
  data exists, stop and ask the user.
- Find how to **reset state** (seed/reset script, clearing localStorage). Every take starts clean.
- Pick 3–5 beats that show the value: hook → action → result → one detail → end. 15–30 s of footage.
- Read the actual components to get stable selectors (ids, `data-testid`, roles). Don't guess.

## 2. Scaffold and script

```bash
screencraft --json init video/ --base-url http://127.0.0.1:3000 --title "Product name"
```
Write `video/scenario.py`: `CONFIG`, optional `login(page, cfg)` and `prepare(page, cfg)`, and
`run(take, page)`. Rules that save retakes:
- `take.mark("name")` at every beat; `take.box("name", selector)` (or `click(..., name=)`) for
  everything the camera or a callout should frame. Always mark `hook` first and `end` last.
- Wait for the app with `page.wait_for_selector(...)` after actions, then `take.hold(0.3–0.8)`.
- Park the pointer away from text before `take.type(...)`; type at `cps` 25–35.
- In `prepare()` hide toasts, cookie banners, dev overlays; close side panels.
- Native `title=` tooltips never render headless — use a plan `callout` instead.

## 3. Record and inspect

```bash
screencraft --json record video/scenario.py --out video/out/footage [--base-url URL]
screencraft --json inspect video/out/footage
```
Check `peak_fps` ≥ 50 on busy beats (lower on macOS → GPU flags issue, see reference) and that every
mark you planned is present. A failed selector raises a Playwright error on stderr: fix the scenario
and record again — footage is cheap (≈ take length + 10 s).

## 4. Plan, compose, look

Write `video/plan.py` using the marks and boxes `inspect` printed (never hard-code seconds):
camera segments that follow the action (zoom 1.4–1.7 on the beat, back to 1.0 between scenes),
one short subtitle per beat (≥ 0.3 s per word, no overlaps), intro/outro cards.

```bash
screencraft --json compose video/plan.py --footage video/out/footage --out video/out/composition
screencraft --json snapshot video/out/composition --at 1,5,9,14 --out video/out/stills
```
Fix every `warnings` entry. **Look at the stills** (read the PNGs / contact sheet): text readable,
camera on the action, nothing cropped, no subtitle covering the thing it describes. Iterate on
plan.py with `compose` + `snapshot` only — no need to record again.

## 5. Render and deliver

Render takes ~4–5 min per 20 s on an M1 — run it in the background with a log file.
```bash
screencraft --json render video/out/composition --out video/out/video.mp4
screencraft --json poster video/out/video.mp4 --at 9.0
```
Confirm the JSON shows `fps: 60` and the expected duration. Hand over the mp4 + poster paths.
`.gitignore` the `out/` dir; commit `scenario.py` + `plan.py` so the video can be re-made after UI changes.

One-shot when scenario and plan are already good:
`screencraft --json make video/scenario.py video/plan.py --out video/out --base-url URL --poster-at 9`
(`--serve DIR` for static sites, `--skip-render` to stop after the check).

## With /brag (or another launch-video skill)

Brag decides the story; screencraft supplies real footage.
1. Run brag's own planning: concept, tone, beats, title, copy. Stop before it builds screenshot scenes.
2. Turn brag's beats into `scenario.py` marks (one mark per beat) and record.
3. Put brag's lines into `plan.py`: hook → `intro.title`, beat captions → `subtitles`,
   closing line / CTA → `outro`; map brag's tone to `look` (polished → graphite/ocean,
   playful → sunset/violet, accent = the app's brand colour from its CSS).
4. Compose, snapshot, render as above into brag's output folder; then let brag write the share copy.
Landscape 16:9 only for now; if brag asked for vertical, say so and render landscape.
