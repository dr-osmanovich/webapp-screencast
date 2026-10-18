# Gotchas (each one cost a take)

- **GPU flags matter.** Headless Chromium with SwiftShader repaints a busy page at ~30 fps under
  screencast; with `--use-angle=metal --enable-gpu-rasterization` (set by default) 55–62 fps on an
  M1. Linux: try `--use-gl=angle --use-angle=vulkan` or `egl`; check `peak_capture_fps` in events.json.
- **Record from a clean app state.** Reset the database or storage before each take; web apps love
  to restore drafts, and typing then lands inside pre-filled text.
- **A static tail paints no frames.** The assembler holds the last frame until the last logged
  event and cuts the video with `-t`; otherwise ffmpeg's concat pads the last image.
- **Native tooltips never paint in headless.** `title=` bubbles are OS widgets. Use a plan `callout`
  (and a `halo`) instead, or give the app a CSS tooltip.
- **Quiet the page in `prepare()`.** Close side panels, hide onboarding toasts, pause live clocks
  if they distract. Do it with `page.add_style_tag` or clicks before `take.start()`.
- **Park the pointer while typing**, otherwise the arrow covers the words.
- **PNG frame extraction is big.** HyperFrames extracts the footage as PNGs: about 2 GB per 25 s of
  4K footage. Pass `--frames-cache-dir` to a scratch disk; it is deleted after the render.
- **Headed mode is slow.** A visible window repaints at ~10 fps under screencast. Use `--headed`
  only to debug selectors.
- **Fonts.** The stage uses a system font stack by default; set `look.font` and ship your own
  web fonts into the composition if the brand needs them.
