# screencraft reference

## CLI (`screencraft [--json] <command>`)

| command | does | JSON result keys |
|---|---|---|
| `doctor` | checks Python 3.11+, Playwright Chromium, ffmpeg/ffprobe, Node 22+, npx | `checks[{name, ok, detail, fix}]` |
| `init DIR [--base-url] [--title] [--force]` | writes `DIR/scenario.py` + `DIR/plan.py` templates | `files` |
| `record SCENARIO --out FOOTAGE [--base-url] [--scale] [--headed]` | runs the scenario, writes `take.mp4` (3840×2160 @60) + `events.json` | `take, events, duration, frames, peak_fps, size` |
| `inspect FOOTAGE` | marks (s), boxes (CSS px), event counts | `duration, marks, boxes, events, viewport` |
| `compose PLAN --footage FOOTAGE --out COMP` | builds the HyperFrames composition | `composition, index, duration, warnings` |
| `snapshot COMP --at 1,5,9 --out DIR` | PNG stills + contact sheet | `snapshots, contact_sheet` |
| `render COMP --out X.mp4 [--quality draft\|looks\|delivery] [--no-check]` | `hyperframes check` then render | `video, size, fps, duration` |
| `poster X.mp4 --at SEC` | bakes that frame as frame 0, writes `X.jpg`, keeps `X.raw.mp4` | `poster, video, raw` |
| `make SCENARIO PLAN --out OUT [--base-url URL \| --serve DIR] [--name] [--poster-at] [--skip-render]` | record → compose → check → render → poster | `footage, composition, video, poster` |
| `demo [--out] [--skip-render]` | the whole pipeline on the bundled demo app | same as `make` |

On failure: `{"ok": false, "error": "..."}`, exit 1 (step failed) or 2 (bad input / missing dependency).

## Scenario module

```python
CONFIG = {"base_url": "http://127.0.0.1:3000", "start_path": "/", "scale": 2,
          "viewport": {"width": 1920, "height": 1080}, "locale": "en-US", "timezone": "UTC",
          "color_scheme": "light", "cursor_start": [1150, 700], "settle": 0.9,
          "wait_until": "networkidle"}
def login(page, cfg): ...      # optional; Playwright page, before start_path opens
def prepare(page, cfg): ...    # optional; after load, before recording starts
def run(take, page): ...       # required
```

`take` (all coordinates CSS px of the viewport):

| call | effect |
|---|---|
| `mark(name)` | names a beat (time) |
| `box(name, selector)` → bbox | logs an element rectangle |
| `box_at(name, bbox)` | logs a rectangle you already have |
| `hold(sec)` | waits (page keeps painting) |
| `place(x, y)` | teleports the pointer |
| `move(x, y, dur=0.6)` | eased pointer move |
| `click(selector, dur=0.6, settle=0.25, name=None)` → bbox | move + press + release; `name` also logs the box |
| `click_at(x, y, dur, settle)` | click at a point |
| `type(text, cps=30, jitter=0.35)` | human-rhythm typing into the focused element |
| `scroll_to(y_page, dur=1.2)` | smooth window scroll (logs `scroll_start`/`scroll_end` marks) |
| `scroll_into_view(selector, offset=300, dur=1.2)` → bbox | scroll so the element sits `offset` px from top |

`page` is the Playwright `Page` — use it for waits (`wait_for_selector`), reading state, or
evaluating JS; real user-visible actions should go through `take` so they are logged and animated.

## Plan module

```python
def plan(ctx):            # ctx.m(mark), ctx.center(box, dx, dy), ctx.box(name) -> {x,y,w,h}, ctx.duration
    return {...}
```

| key | meaning |
|---|---|
| `camera` | `[{from, zoom, focus}]`; last segment with `from` ≤ t wins. `focus`: `"cursor"`, `"center"`, a box name, or `ctx.center(...)`. Start with `{"from": -99, "zoom": 1.0, "focus": "center"}` |
| `subtitles` | `[[start, end, text]]` in footage seconds; warns under 0.3 s/word or on overlap |
| `intro` | `{title, subtitle, duration}` (title may contain `<b>`) |
| `outro` | `{title, line, duration, overlap, subtitle, logo}` |
| `callouts` | `[{at, until, html, x, y, side: "below"\|"left"}]` |
| `halos` | `[{at, box}]` — a ring pulse on a logged box |
| `look` | `wallpaper` (`violet`, `mint`, `sunset`, `ocean`, `graphite` or CSS background), `accent`, `radius`, `cursor_size`, `font`, `focus_omega` (5.2), `zoom_omega` (4.2) |
| `tag` | small label pinned on top |
| `music`, `sfx`, `key_sfx`, `click_sfx` | audio files (copied in); clicks/keys timed from the event log |
| `video_start`, `media_start`, `video_end`, `cursor_end` | trims; default from `hook`/`end` marks |
| `canvas`, `padding`, `fps` | default 1920×1080, 0.05, 60 |
| `title`, `lang` | composition metadata |

## Gotchas

- Peak capture below ~50 fps on macOS: the default GPU flags were overridden — unset
  `SCREENCRAFT_CHROMIUM_ARGS`. Linux repaints slower; try `SCREENCRAFT_CHROMIUM_ARGS="--use-gl=angle --use-angle=vulkan"`.
- Static stretches paint no frames — that's fine; frames are held.
- Restore-on-load apps (drafts, last search): reset state or clear storage in `login`/`prepare`.
- Rendering extracts PNGs (~2 GB per 25 s of 4K): `render --frames-cache-dir /big/disk`.
- `--headed` repaints ~10 fps — only for debugging selectors, never for the final take.
