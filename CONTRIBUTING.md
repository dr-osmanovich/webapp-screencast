# Contributing

Small project, small rules.

- Python 3.11+, no dependencies beyond Playwright; `ffmpeg` and Node 22+ (for HyperFrames) on PATH.
- `pip install -e .` then `playwright install chromium` and `screencraft demo --skip-render` to
  check capture and compose; `screencraft demo` for the full render.
- Keep the runtime (`src/screencraft/assets/studio.js`) a pure function of time: no `Date`, no
  `Math.random`, no state that depends on seek order. HyperFrames renders frames out of order.
- Everything project-specific belongs in a scenario or a plan, not in the package.
- This is an independent implementation. Do not copy code, assets, wallpapers or UI text from
  proprietary screen-recording products.
- Bug reports: attach `events.json` and the `check` output; they describe the take precisely.
