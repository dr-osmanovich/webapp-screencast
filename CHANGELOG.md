# Changelog

## 0.3.0 — 2026-10-19

Renamed from screencraft to **webapp-screencast**. No behaviour changes.

- Package `webapp-screencast` (import `webapp_screencast`), CLI `webapp-screencast`.
- Repository `dr-osmanovich/webapp-screencast`; skill `webapp-screencast`
  (`npx skills add dr-osmanovich/webapp-screencast`).
- Environment variable `SCREENCRAFT_CHROMIUM_ARGS` is now `WEBAPP_SCREENCAST_CHROMIUM_ARGS`.

## 0.2.0 — 2026-10-19

Agent-first release.

- Agent skill in `skills/screencraft/` (install: `npx skills add dr-osmanovich/screencraft`), with a
  CLI/API reference and a recipe for pairing with /brag.
- `--json` global flag: one JSON result object on stdout, progress on stderr; exit codes 0/1/2.
- New commands: `init` (scaffold scenario + plan), `inspect` (marks, boxes, duration),
  `doctor` (dependency check with fixes), `make` (whole pipeline, `--serve DIR` for static sites).
- `AGENTS.md` for agents working on screencraft itself.

## 0.1.0 — 2026-10-18

First public version.

- `screencraft record`: headless 60 fps capture of a scripted web session via CDP screencast, with
  an event log of pointer, keys, scrolls, marks and element boxes.
- `screencraft compose`: plan-driven HyperFrames composition — wallpaper stage, spring camera,
  re-rendered cursor with click rings, subtitles, intro/outro cards, callouts, halos, SFX, music.
- `screencraft render` / `snapshot` / `poster`: thin wrappers over HyperFrames and ffmpeg.
- `screencraft demo`: a bundled single-page app and a 16-second scenario to try it end to end.
