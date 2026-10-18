# Changelog

## 0.1.0 — 2026-10-18

First public version, extracted from an internal pipeline used for product videos.

- `screencraft record`: headless 60 fps capture of a scripted web session via CDP screencast, with
  an event log of pointer, keys, scrolls, marks and element boxes.
- `screencraft compose`: plan-driven HyperFrames composition — wallpaper stage, spring camera,
  re-rendered cursor with click rings, subtitles, intro/outro cards, callouts, halos, SFX, music.
- `screencraft render` / `snapshot` / `poster`: thin wrappers over HyperFrames and ffmpeg.
- `screencraft demo`: a bundled single-page app and a 16-second scenario to try it end to end.
