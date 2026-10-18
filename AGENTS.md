# AGENTS.md

Guide for coding agents working **on** screencraft. To **use** screencraft to make a video, follow
[skills/screencraft/SKILL.md](skills/screencraft/SKILL.md) (installable with
`npx skills add dr-osmanovich/screencraft`).

## Layout

- `src/screencraft/capture.py` — Playwright + CDP screencast recorder (`Take`), `run_scenario`.
- `src/screencraft/compose.py` — `plan.py` + footage → HyperFrames composition (`index.html`, assets).
- `src/screencraft/assets/studio.js|css` — browser runtime: stage, spring camera, cursor, subtitles, cards.
- `src/screencraft/render.py` — `npx hyperframes` check/render/snapshot, ffmpeg poster.
- `src/screencraft/cli.py` — CLI; every command returns a dict that `--json` prints.
- `src/screencraft/templates/` — composition template and `init` scaffolds.
- `src/screencraft/examples/` — bundled demo app, scenario and plan (used by `screencraft demo` and CI).
- `skills/screencraft/` — the agent skill (SKILL.md + reference.md). Keep it in sync with CLI changes.

## Dev loop

```bash
python3 -m venv .venv && .venv/bin/pip install -e . && .venv/bin/python -m playwright install chromium
.venv/bin/screencraft doctor
.venv/bin/screencraft --json demo --skip-render      # capture + compose + check, ~40 s
.venv/bin/screencraft snapshot out/demo/composition --at 3,9,14 --out out/stills   # look at them
```
A full render (`screencraft demo`) takes ~4 min; run it in the background with a log file.
CI (`.github/workflows/ci.yml`) runs `demo --skip-render` + `hyperframes check` on Ubuntu.

## Rules

- Clean-room: never copy code, assets or text from Screen Studio or other closed tools.
- The composition must stay seek-safe: everything is a pure function of time on one paused GSAP
  timeline — no `Date.now()`, no free-running animations.
- New CLI output goes through `log()` (stderr in `--json` mode) and the command's returned dict.
- Update README, `skills/screencraft/reference.md` and CHANGELOG together with behaviour changes.
- No real personal data in examples, fixtures or screenshots.
