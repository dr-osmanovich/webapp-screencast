"""screencraft command line: record → compose → render → poster, plus a self-contained demo."""
from __future__ import annotations

import argparse
import http.server
import os
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import __version__
from .capture import run_scenario
from .compose import compose
from .render import bake_poster, check, render, snapshot

PKG = Path(__file__).resolve().parent
EXAMPLES = PKG / "examples"


def _frames_dir(explicit: str | None, name: str) -> Path:
    if explicit:
        return Path(explicit)
    return Path(tempfile.gettempdir()) / "screencraft-frames" / name


def cmd_record(a: argparse.Namespace) -> int:
    out = Path(a.out)
    frames = _frames_dir(a.frames_dir, out.name or "take")
    if frames.exists():
        for p in frames.glob("*"):
            p.unlink()
    run_scenario(Path(a.scenario), out, frames, scale=a.scale, base_url=a.base_url, headless=not a.headed)
    if not a.keep_frames:
        for p in frames.glob("*"):
            p.unlink()
    return 0


def cmd_compose(a: argparse.Namespace) -> int:
    compose(Path(a.plan), Path(a.footage), Path(a.out))
    return 0


def cmd_render(a: argparse.Namespace) -> int:
    comp = Path(a.composition)
    if not a.no_check:
        rc = check(comp)
        if rc != 0:
            print("hyperframes check failed; fix the errors or pass --no-check", file=sys.stderr)
            return rc
    return render(comp, Path(a.out), fps=a.fps, quality=a.quality, frames_cache_dir=a.frames_cache_dir)


def cmd_snapshot(a: argparse.Namespace) -> int:
    return snapshot(Path(a.composition), [float(x) for x in a.at.split(",")], Path(a.out))


def cmd_poster(a: argparse.Namespace) -> int:
    jpg = bake_poster(Path(a.video), a.at)
    print(f"poster: {jpg}  (frame 0 baked; original kept as .raw.mp4)")
    return 0


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401 - silence
        pass


def _serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    handler = lambda *args, **kw: _Quiet(*args, directory=str(directory), **kw)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def cmd_demo(a: argparse.Namespace) -> int:
    """Record, compose and render the bundled demo app end to end."""
    ex = Path(a.examples) if a.examples else EXAMPLES
    app, scen, plan = ex / "demo-app", ex / "demo" / "scenario.py", ex / "demo" / "plan.py"
    for p in (app, scen, plan):
        if not p.exists():
            print(f"missing {p}; run from a source checkout or pass --examples", file=sys.stderr); return 2
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    srv, port = _serve(app)
    print(f"demo app on http://127.0.0.1:{port}")
    try:
        run_scenario(scen, out / "footage", _frames_dir(None, "demo"), base_url=f"http://127.0.0.1:{port}", scale=a.scale)
    finally:
        srv.shutdown()
    compose(plan, out / "footage", out / "composition")
    if a.skip_render:
        print("composition ready; render with: screencraft render", out / "composition", "--out", out / "demo.mp4")
        return 0
    rc = check(out / "composition")
    if rc != 0:
        return rc
    rc = render(out / "composition", out / "demo.mp4", fps=a.fps, quality=a.quality)
    if rc == 0:
        bake_poster(out / "demo.mp4", a.poster_at)
        print(f"done: {out / 'demo.mp4'}")
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="screencraft", description="Scriptable Screen-Studio-style videos of web apps.")
    p.add_argument("--version", action="version", version=f"screencraft {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="run a scenario against a web app and record 60 fps footage + events")
    r.add_argument("scenario", help="scenario .py (CONFIG, login(), prepare(), run(take, page))")
    r.add_argument("--out", required=True, help="footage directory (take.mp4, events.json)")
    r.add_argument("--base-url", help="override CONFIG['base_url']")
    r.add_argument("--scale", type=float, help="device scale factor (default 2 → 3840×2160 footage)")
    r.add_argument("--frames-dir", help="where raw JPEG frames go (default: system temp)")
    r.add_argument("--keep-frames", action="store_true")
    r.add_argument("--headed", action="store_true", help="show the browser (slower repaint; for debugging)")
    r.set_defaults(fn=cmd_record)

    c = sub.add_parser("compose", help="build a HyperFrames composition from footage + plan.py")
    c.add_argument("plan"); c.add_argument("--footage", required=True); c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_compose)

    n = sub.add_parser("render", help="hyperframes check + render (mp4)")
    n.add_argument("composition"); n.add_argument("--out", required=True)
    n.add_argument("--fps", type=int, default=60); n.add_argument("--quality", default="delivery", help="draft | looks | delivery")
    n.add_argument("--no-check", action="store_true"); n.add_argument("--frames-cache-dir")
    n.set_defaults(fn=cmd_render)

    s = sub.add_parser("snapshot", help="PNG stills of the composition at given seconds")
    s.add_argument("composition"); s.add_argument("--at", required=True, help="comma-separated seconds"); s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_snapshot)

    o = sub.add_parser("poster", help="bake the frame at --at as the poster / frame 0")
    o.add_argument("video"); o.add_argument("--at", type=float, required=True)
    o.set_defaults(fn=cmd_poster)

    d = sub.add_parser("demo", help="record + compose + render the bundled demo app")
    d.add_argument("--out", default="out/demo"); d.add_argument("--scale", type=float, default=2)
    d.add_argument("--fps", type=int, default=60); d.add_argument("--quality", default="delivery")
    d.add_argument("--poster-at", type=float, default=9.0); d.add_argument("--skip-render", action="store_true")
    d.add_argument("--examples", help="path to an examples/ directory")
    d.set_defaults(fn=cmd_demo)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
