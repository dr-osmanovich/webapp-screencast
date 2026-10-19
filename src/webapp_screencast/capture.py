"""Headless real-footage capture for web apps.

A scenario drives the page with human-paced actions while CDP ``Page.startScreencast`` streams
frames (no OS screen-recording permission needed). Static stretches paint no frames; every frame
is held for its real duration, so the assembled 60 fps video has exact timing. Every pointer move,
press/release, key, scroll and named mark is logged on the same epoch clock the frames carry.

The pointer is *not* in the footage (headless): the composition re-renders it on a spring, which is
what makes the final video read as smooth.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import math
import random
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import Page, sync_playwright

# Hardware GPU inside headless Chromium. On macOS (Metal via ANGLE) a busy page repaints at ~30 fps
# under screencast without these flags and 55-62 fps with them (Apple M1). Other platforms get no
# special flags by default; override with WEBAPP_SCREENCAST_CHROMIUM_ARGS="--flag --flag".
import os as _os
import sys as _sys

if _os.environ.get("WEBAPP_SCREENCAST_CHROMIUM_ARGS"):
    GPU_ARGS = _os.environ["WEBAPP_SCREENCAST_CHROMIUM_ARGS"].split()
elif _sys.platform == "darwin":
    GPU_ARGS = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--use-gl=angle", "--use-angle=metal", "--enable-zero-copy"]
else:
    GPU_ARGS = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization"]
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}


def _ease_in_out(u: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * u)


class Take:
    """One continuous recording with an event log. Create via :func:`run_scenario`."""

    def __init__(self, page: Page, frames_dir: Path, *, scale: float = 2, jpeg_quality: int = 95,
                 viewport: dict | None = None):
        self.page, self.scale = page, scale
        self.viewport = viewport or DEFAULT_VIEWPORT
        self.frames_dir = Path(frames_dir)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.frames: list[tuple[float, str]] = []
        self.events: list[dict[str, Any]] = []
        self.cursor = (self.viewport["width"] * 0.6, self.viewport["height"] * 0.6)
        self.quality = jpeg_quality
        self.t_start: float | None = None
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._on_frame)

    # ---- frames ---------------------------------------------------------------------------
    def _on_frame(self, ev: dict) -> None:
        i = len(self.frames)
        path = self.frames_dir / f"f{i:05d}.jpg"
        path.write_bytes(base64.b64decode(ev["data"]))
        self.frames.append((ev["metadata"]["timestamp"], str(path)))
        self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

    def start(self) -> None:
        """Begin streaming frames. Call once; the runner does it for you."""
        self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": self.quality,
            "maxWidth": int(self.viewport["width"] * self.scale),
            "maxHeight": int(self.viewport["height"] * self.scale),
            "everyNthFrame": 1,
        })
        self.t_start = time.time()
        # nudge one repaint so the first frame arrives immediately
        self.page.evaluate(
            "() => { document.documentElement.style.opacity='0.999';"
            " requestAnimationFrame(() => { document.documentElement.style.opacity=''; }); }")
        self.hold(0.3)

    # ---- event log ------------------------------------------------------------------------
    def log(self, kind: str, **kw: Any) -> None:
        self.events.append({"t": time.time(), "type": kind, **kw})

    def mark(self, name: str) -> None:
        """Name a beat; the composer reads marks to place camera moves, subtitles and sound."""
        self.log("mark", name=name)

    def box(self, name: str, selector: str) -> dict | None:
        """Log the viewport box of an element so the camera can frame it later."""
        bb = self.page.locator(selector).first.bounding_box()
        if bb:
            self.log("box", name=name, x=bb["x"], y=bb["y"], w=bb["width"], h=bb["height"])
        return bb

    def box_at(self, name: str, bb: dict) -> None:
        self.log("box", name=name, x=bb["x"], y=bb["y"], w=bb.get("w", bb.get("width")), h=bb.get("h", bb.get("height")))

    # ---- actions (human-paced, all logged) -----------------------------------------------
    def hold(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000))

    def place(self, x: float, y: float) -> None:
        """Teleport the pointer (use before start, or between scenes)."""
        self.page.mouse.move(x, y)
        self.cursor = (x, y)
        self.log("move", x=x, y=y)

    def move(self, x: float, y: float, dur: float = 0.6) -> None:
        """Straight path, ease-in-out, ~60 samples/s with absolute pacing (no drift)."""
        x0, y0 = self.cursor
        n = max(6, int(dur * 60))
        t0 = time.time()
        for i in range(1, n + 1):
            e = _ease_in_out(i / n)
            px, py = x0 + (x - x0) * e, y0 + (y - y0) * e
            self.page.mouse.move(px, py)
            self.log("move", x=px, y=py)
            dt = t0 + dur * i / n - time.time()
            if dt > 0:
                time.sleep(dt)
        self.cursor = (x, y)

    def click_at(self, x: float, y: float, dur: float = 0.6, settle: float = 0.25) -> None:
        self.move(x, y, dur)
        self.hold(settle)
        self.page.mouse.down(); self.log("down", x=x, y=y)
        self.hold(0.09)
        self.page.mouse.up(); self.log("up", x=x, y=y)

    def click(self, selector: str, dur: float = 0.6, settle: float = 0.25, name: str | None = None) -> dict:
        """Move to the element's centre and click it. ``name`` also logs its box."""
        bb = self.page.locator(selector).first.bounding_box()
        if not bb:
            raise RuntimeError(f"no bounding box for {selector!r}")
        if name:
            self.log("box", name=name, x=bb["x"], y=bb["y"], w=bb["width"], h=bb["height"])
        self.click_at(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, dur, settle)
        return bb

    def type(self, text: str, cps: float = 30.0, jitter: float = 0.35) -> None:
        """Per-character typing with a human rhythm; longer pauses after punctuation."""
        base = 1.0 / cps
        for ch in text:
            self.page.keyboard.type(ch)
            self.log("key", ch=ch)
            d = base * (1 + random.uniform(-jitter, jitter))
            if ch in ".,;:!?":
                d += base * 2.5
            elif ch == " ":
                d += base * 0.4
            time.sleep(d)

    def scroll_to(self, y_page: float, dur: float = 1.2) -> None:
        """Smooth window scroll driven by requestAnimationFrame inside the page."""
        self.log("scroll_start", y=y_page, dur=dur)
        self.page.evaluate(
            """([y, ms]) => new Promise(res => { const y0 = window.scrollY, dy = y - y0, t0 = performance.now();
                 const step = (now) => { const u = Math.min(1, (now - t0) / ms); const e = 0.5 - 0.5 * Math.cos(Math.PI * u);
                   window.scrollTo(0, y0 + dy * e); if (u < 1) requestAnimationFrame(step); else res(); };
                 requestAnimationFrame(step); })""",
            [y_page, int(dur * 1000)],
        )
        self.log("scroll_end", y=y_page)

    def scroll_into_view(self, selector: str, offset: float = 300, dur: float = 1.2) -> dict:
        """Scroll so the element sits ``offset`` px below the top; returns its box afterwards."""
        loc = self.page.locator(selector).first
        loc.wait_for(state="attached")
        y_abs = self.page.evaluate("el => el.getBoundingClientRect().top + window.scrollY", loc.element_handle())
        self.scroll_to(max(0, y_abs - offset), dur)
        self.hold(0.3)
        return loc.bounding_box()

    # ---- finish ---------------------------------------------------------------------------
    def stop(self, mp4: Path, events_json: Path, *, crf: int = 14, tail_hold: float = 0.5) -> dict:
        """Stop streaming, assemble a constant-60fps H.264 master, write events.json."""
        self.hold(tail_hold)
        self.cdp.send("Page.stopScreencast")
        fr = self.frames
        if len(fr) < 2:
            raise RuntimeError("too few frames captured; did the page paint?")
        t0 = fr[0][0]
        # A static tail paints no frames: hold the last frame until the last logged event.
        last_event = max((e["t"] for e in self.events), default=fr[-1][0])
        tail_hold = max(tail_hold, last_event - fr[-1][0] + tail_hold)
        lines = []
        for k, (ts, path) in enumerate(fr):
            nxt = fr[k + 1][0] if k + 1 < len(fr) else ts + tail_hold
            lines.append(f"file '{path}'\nduration {max(nxt - ts, 0.001):.5f}")
        lines.append(f"file '{fr[-1][1]}'\nduration 0.01667")   # concat needs a trailing entry
        lst = self.frames_dir / "list.txt"
        lst.write_text("\n".join(lines))
        w, h = int(self.viewport["width"] * self.scale), int(self.viewport["height"] * self.scale)
        total = (fr[-1][0] - t0) + tail_hold    # ffmpeg pads the last image past its duration; cut exactly here
        mp4 = Path(mp4); mp4.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-t", f"{total:.4f}",
            "-vf", f"fps=60,scale={w}:{h}:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-g", "60", "-movflags", "+faststart", str(mp4),
        ], check=True)
        events = [{**e, "t": round(e["t"] - t0, 4)} for e in self.events]
        ts = [f[0] for f in fr]
        peak = 0
        for i in range(len(ts)):
            j = i
            while j < len(ts) and ts[j] - ts[i] <= 1.0:
                j += 1
            peak = max(peak, j - i)
        meta = {
            "video": mp4.name, "width": w, "height": h, "fps": 60, "scale": self.scale,
            "css_viewport": self.viewport, "duration": round(total, 3), "frames_captured": len(fr),
            "peak_capture_fps": peak, "first_frame_delay": round(t0 - (self.t_start or t0), 3),
            "events": events,
        }
        Path(events_json).write_text(json.dumps(meta, ensure_ascii=False, indent=0))
        return meta


# ---- scenario runner ------------------------------------------------------------------------

def load_module(path: Path, name: str = "scenario"):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_scenario(scenario_path: Path, out_dir: Path, frames_dir: Path, *, scale: float | None = None,
                 base_url: str | None = None, headless: bool = True, log: Callable[[str], None] = print) -> dict:
    """Run a scenario module and write ``out_dir/take.mp4`` + ``out_dir/events.json``.

    A scenario module may define::

        CONFIG = {"base_url": "http://127.0.0.1:8765", "start_path": "/", "scale": 2,
                  "viewport": {"width": 1920, "height": 1080}, "locale": "en-US",
                  "timezone": "UTC", "jpeg_quality": 95, "cursor_start": [1150, 650]}
        def login(page, cfg): ...     # optional, before start_path is opened
        def prepare(page, cfg): ...   # optional, after the page loaded (hide toasts, close panels)
        def run(take, page): ...      # required: the storyboard as take.* actions
    """
    mod = load_module(Path(scenario_path))
    cfg = dict(getattr(mod, "CONFIG", {}))
    if base_url:
        cfg["base_url"] = base_url
    if scale:
        cfg["scale"] = scale
    cfg.setdefault("scale", 2)
    cfg.setdefault("viewport", DEFAULT_VIEWPORT)
    cfg.setdefault("start_path", "/")
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=GPU_ARGS if headless else [])
        ctx = browser.new_context(viewport=cfg["viewport"], device_scale_factor=cfg["scale"],
                                  locale=cfg.get("locale", "en-US"), timezone_id=cfg.get("timezone", "UTC"),
                                  color_scheme=cfg.get("color_scheme", "light"))
        page = ctx.new_page()
        if hasattr(mod, "login"):
            mod.login(page, cfg)
        if cfg.get("base_url"):
            page.goto(cfg["base_url"].rstrip("/") + cfg["start_path"], wait_until=cfg.get("wait_until", "networkidle"))
        if hasattr(mod, "prepare"):
            mod.prepare(page, cfg)
        page.wait_for_timeout(int(cfg.get("settle", 0.9) * 1000))
        take = Take(page, frames_dir, scale=cfg["scale"], jpeg_quality=cfg.get("jpeg_quality", 95), viewport=cfg["viewport"])
        cx, cy = cfg.get("cursor_start", (cfg["viewport"]["width"] * 0.6, cfg["viewport"]["height"] * 0.6))
        take.place(cx, cy)
        take.start()
        mod.run(take, page)
        meta = take.stop(out_dir / "take.mp4", out_dir / "events.json")
        browser.close()
    marks = [(e["name"], e["t"]) for e in meta["events"] if e["type"] == "mark"]
    log(f"take: {meta['duration']} s, {meta['frames_captured']} frames, peak {meta['peak_capture_fps']} fps, "
        f"{meta['width']}x{meta['height']} → {out_dir / 'take.mp4'}")
    log("marks: " + ", ".join(f"{n}@{t:.2f}" for n, t in marks))
    return meta
