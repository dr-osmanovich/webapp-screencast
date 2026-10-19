"""webapp-screencast command line: record → compose → render → poster, plus a self-contained demo.

Built to be driven by coding agents as much as by people:
- ``--json`` (before the subcommand) prints one JSON object on stdout; all progress goes to stderr.
- ``init`` scaffolds scenario.py + plan.py, ``inspect`` lists marks/boxes, ``doctor`` checks dependencies,
  ``make`` runs the whole pipeline in one call.
- Exit codes: 0 ok, 1 step failed, 2 bad input or missing dependency.
"""
from __future__ import annotations

import argparse
import http.server
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import __version__
from .capture import run_scenario
from .compose import compose, load_footage
from .render import bake_poster, check, render, snapshot

PKG = Path(__file__).resolve().parent
EXAMPLES = PKG / "examples"
TEMPLATES = PKG / "templates"

JSON = False  # set by --json


def log(msg: str = "") -> None:
    print(msg, file=sys.stderr if JSON else sys.stdout, flush=True)


def _sub_out():
    """Where child processes (npx hyperframes) write: stderr in --json mode, so stdout stays parseable."""
    return sys.stderr if JSON else None


class Fail(Exception):
    def __init__(self, msg: str, code: int = 1, **extra):
        super().__init__(msg); self.code = code; self.extra = extra


def _frames_dir(explicit: str | None, name: str) -> Path:
    if explicit:
        return Path(explicit)
    return Path(tempfile.gettempdir()) / "webapp-screencast-frames" / name


def _clear(d: Path) -> None:
    if d.exists():
        for p in d.glob("*"):
            p.unlink()


def _take_summary(meta: dict, out: Path) -> dict:
    return {"take": str(out / "take.mp4"), "events": str(out / "events.json"), "duration": meta["duration"],
            "frames": meta["frames_captured"], "peak_fps": meta["peak_capture_fps"],
            "size": [meta["width"], meta["height"]]}


def _record(scenario: Path, out: Path, frames: Path, *, scale=None, base_url=None, headed=False, keep=False) -> dict:
    if not scenario.exists():
        raise Fail(f"scenario not found: {scenario}", 2)
    _clear(frames)
    meta = run_scenario(scenario, out, frames, scale=scale, base_url=base_url, headless=not headed, log=log)
    if not keep:
        _clear(frames)
    return _take_summary(meta, out)


def _compose(plan: Path, footage: Path, out: Path) -> dict:
    if not plan.exists():
        raise Fail(f"plan not found: {plan}", 2)
    if not (footage / "events.json").exists():
        raise Fail(f"no events.json in {footage}; run `webapp-screencast record` first", 2)
    warnings: list[str] = []

    def clog(msg: str) -> None:
        if msg.startswith("  "):
            warnings.append(msg.strip())
        log(msg)

    res = compose(plan, footage, out, log=clog)
    return {"composition": str(out), "index": str(out / "index.html"), "duration": res["duration"],
            "warnings": warnings}


def _check(comp: Path) -> None:
    rc = check(comp, stdout=_sub_out())
    if rc != 0:
        raise Fail("hyperframes check failed; fix the errors above or pass --no-check", rc or 1)


def _render(comp: Path, out: Path, *, fps: int, quality: str, frames_cache_dir=None) -> dict:
    rc = render(comp, out, fps=fps, quality=quality, frames_cache_dir=frames_cache_dir, stdout=_sub_out())
    if rc != 0:
        raise Fail("hyperframes render failed", rc)
    return {"video": str(out.resolve()), **_probe(out)}


def _probe(video: Path) -> dict:
    if shutil.which("ffprobe") is None:
        return {}
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(video)],
                       capture_output=True, text=True)
    try:
        j = json.loads(r.stdout); s = j["streams"][0]; num, den = s["r_frame_rate"].split("/")
        return {"size": [s["width"], s["height"]], "fps": round(int(num) / int(den), 2),
                "duration": round(float(j["format"]["duration"]), 2)}
    except (KeyError, IndexError, ValueError):
        return {}


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_record(a) -> dict:
    out = Path(a.out)
    return _record(Path(a.scenario), out, _frames_dir(a.frames_dir, out.name or "take"),
                   scale=a.scale, base_url=a.base_url, headed=a.headed, keep=a.keep_frames)


def cmd_compose(a) -> dict:
    return _compose(Path(a.plan), Path(a.footage), Path(a.out))


def cmd_render(a) -> dict:
    comp = Path(a.composition)
    if not a.no_check:
        _check(comp)
    return _render(comp, Path(a.out), fps=a.fps, quality=a.quality, frames_cache_dir=a.frames_cache_dir)


def cmd_snapshot(a) -> dict:
    out = Path(a.out)
    rc = snapshot(Path(a.composition), [float(x) for x in a.at.split(",")], out, stdout=_sub_out())
    if rc != 0:
        raise Fail("hyperframes snapshot failed", rc)
    return {"snapshots": sorted(str(p) for p in out.glob("*.png")),
            "contact_sheet": str(out / "contact-sheet.jpg") if (out / "contact-sheet.jpg").exists() else None}


def cmd_poster(a) -> dict:
    jpg = bake_poster(Path(a.video), a.at)
    log(f"poster: {jpg}  (frame 0 baked; original kept as .raw.mp4)")
    return {"poster": str(jpg), "video": str(Path(a.video)), "raw": str(Path(a.video).with_suffix(".raw.mp4"))}


def cmd_init(a) -> dict:
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    title = a.title or d.resolve().name.replace("-", " ").replace("_", " ").title()
    files = {"scenario.py": ("scenario.py.tmpl", {"@@BASE_URL@@": a.base_url}),
             "plan.py": ("plan.py.tmpl", {"@@TITLE@@": title})}
    written = []
    for name, (tmpl, subs) in files.items():
        dst = d / name
        if dst.exists() and not a.force:
            raise Fail(f"{dst} exists; pass --force to overwrite", 2)
        text = (TEMPLATES / tmpl).read_text()
        for k, v in subs.items():
            text = text.replace(k, v)
        dst.write_text(text); written.append(str(dst))
    log("wrote " + ", ".join(written))
    log(f"next: edit run() in scenario.py, then  webapp-screencast make {d}/scenario.py {d}/plan.py --out {d}/out")
    return {"files": written}


def cmd_inspect(a) -> dict:
    footage = Path(a.footage)
    if not (footage / "events.json").exists():
        raise Fail(f"no events.json in {footage}", 2)
    meta, ctx = load_footage(footage)
    counts: dict[str, int] = {}
    for e in meta["events"]:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    res = {"duration": ctx.duration, "size": [meta["width"], meta["height"]],
           "viewport": meta.get("css_viewport"), "scale": meta.get("scale"),
           "marks": {k: round(v, 3) for k, v in sorted(ctx.marks.items(), key=lambda kv: kv[1])},
           "boxes": {k: {kk: round(vv, 1) for kk, vv in b.items()} for k, b in ctx.boxes.items()},
           "events": counts}
    if not JSON:
        log(f"duration {res['duration']} s, footage {res['size'][0]}x{res['size'][1]}")
        log("marks:"); [log(f"  {k:<16} {v:7.3f}") for k, v in res["marks"].items()]
        log("boxes (CSS px):"); [log(f"  {k:<16} x={b['x']} y={b['y']} w={b['w']} h={b['h']}") for k, b in res["boxes"].items()]
        log("events: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return res


def _node_major() -> int | None:
    if shutil.which("node") is None:
        return None
    r = subprocess.run(["node", "--version"], capture_output=True, text=True)
    m = re.match(r"v(\d+)", r.stdout.strip())
    return int(m.group(1)) if m else None


def cmd_doctor(a) -> dict:
    checks = []

    def add(name, ok, detail, fix=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "fix": fix if not ok else ""})

    add("python", sys.version_info >= (3, 11), sys.version.split()[0], "use Python 3.11+")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = Path(p.chromium.executable_path)
        add("chromium", exe.exists(), str(exe), "python -m playwright install chromium")
    except Exception as e:  # noqa: BLE001 - report any failure as a failed check
        add("chromium", False, str(e).splitlines()[0][:160], "pip install playwright && python -m playwright install chromium")
    for tool in ("ffmpeg", "ffprobe"):
        add(tool, shutil.which(tool), shutil.which(tool) or "not on PATH", "install ffmpeg (brew install ffmpeg / apt install ffmpeg)")
    nm = _node_major()
    add("node>=22", nm is not None and nm >= 22, f"v{nm}" if nm else "not on PATH", "install Node.js 22+ (HyperFrames needs it)")
    add("npx", shutil.which("npx"), shutil.which("npx") or "not on PATH", "comes with Node.js")
    ok = all(c["ok"] for c in checks)
    if not JSON:
        for c in checks:
            log(f"{'ok ' if c['ok'] else 'NO '} {c['name']:<9} {c['detail']}" + (f"   → {c['fix']}" if c["fix"] else ""))
    if not ok:
        raise Fail("missing dependencies", 2, checks=checks)
    return {"checks": checks}


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


def _pipeline(scenario: Path, plan: Path, out: Path, *, base_url=None, serve=None, scale=None,
              fps=60, quality="delivery", skip_render=False, no_check=False, poster_at=None, name="video") -> dict:
    out.mkdir(parents=True, exist_ok=True)
    srv = None
    if serve:
        srv, port = _serve(Path(serve)); base_url = f"http://127.0.0.1:{port}"
        log(f"serving {serve} on {base_url}")
    try:
        res = {"footage": _record(scenario, out / "footage", _frames_dir(None, out.resolve().name), scale=scale, base_url=base_url)}
    finally:
        if srv:
            srv.shutdown()
    res["composition"] = _compose(plan, out / "footage", out / "composition")
    if not no_check:
        _check(out / "composition")
    if skip_render:
        log(f"composition ready; render with: webapp-screencast render {out / 'composition'} --out {out / (name + '.mp4')}")
        return res
    res["video"] = _render(out / "composition", out / f"{name}.mp4", fps=fps, quality=quality)
    if poster_at is not None:
        res["poster"] = str(bake_poster(out / f"{name}.mp4", poster_at))
    log(f"done: {out / (name + '.mp4')}")
    return res


def cmd_make(a) -> dict:
    return _pipeline(Path(a.scenario), Path(a.plan), Path(a.out), base_url=a.base_url, serve=a.serve, scale=a.scale,
                     fps=a.fps, quality=a.quality, skip_render=a.skip_render, no_check=a.no_check,
                     poster_at=a.poster_at, name=a.name)


def cmd_demo(a) -> dict:
    """Record, compose and render the bundled demo app end to end."""
    ex = Path(a.examples) if a.examples else EXAMPLES
    app, scen, plan = ex / "demo-app", ex / "demo" / "scenario.py", ex / "demo" / "plan.py"
    for p in (app, scen, plan):
        if not p.exists():
            raise Fail(f"missing {p}; run from a source checkout or pass --examples", 2)
    return _pipeline(scen, plan, Path(a.out), serve=app, scale=a.scale, fps=a.fps, quality=a.quality,
                     skip_render=a.skip_render, poster_at=a.poster_at, name="demo")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="webapp-screencast", description="Scriptable Screen-Studio-style videos of web apps.")
    p.add_argument("--version", action="version", version=f"webapp-screencast {__version__}")
    p.add_argument("--json", action="store_true", help="print one JSON result object on stdout; progress goes to stderr")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="scaffold scenario.py + plan.py in a directory")
    i.add_argument("dir"); i.add_argument("--base-url", default="http://127.0.0.1:3000")
    i.add_argument("--title"); i.add_argument("--force", action="store_true")
    i.set_defaults(fn=cmd_init)

    r = sub.add_parser("record", help="run a scenario against a web app and record 60 fps footage + events")
    r.add_argument("scenario", help="scenario .py (CONFIG, login(), prepare(), run(take, page))")
    r.add_argument("--out", required=True, help="footage directory (take.mp4, events.json)")
    r.add_argument("--base-url", help="override CONFIG['base_url']")
    r.add_argument("--scale", type=float, help="device scale factor (default 2 → 3840×2160 footage)")
    r.add_argument("--frames-dir", help="where raw JPEG frames go (default: system temp)")
    r.add_argument("--keep-frames", action="store_true")
    r.add_argument("--headed", action="store_true", help="show the browser (slower repaint; for debugging)")
    r.set_defaults(fn=cmd_record)

    x = sub.add_parser("inspect", help="list marks, boxes and duration of recorded footage (to write plan.py)")
    x.add_argument("footage"); x.set_defaults(fn=cmd_inspect)

    c = sub.add_parser("compose", help="build a HyperFrames composition from footage + plan.py")
    c.add_argument("plan"); c.add_argument("--footage", required=True); c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_compose)

    n = sub.add_parser("render", help="hyperframes check + render (mp4)")
    n.add_argument("composition"); n.add_argument("--out", required=True)
    n.add_argument("--fps", type=int, default=60); n.add_argument("--quality", default="delivery", help="draft | looks | delivery")
    n.add_argument("--no-check", action="store_true"); n.add_argument("--frames-cache-dir")
    n.set_defaults(fn=cmd_render)

    s = sub.add_parser("snapshot", help="PNG stills of the composition at given seconds (to review before rendering)")
    s.add_argument("composition"); s.add_argument("--at", required=True, help="comma-separated seconds"); s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_snapshot)

    o = sub.add_parser("poster", help="bake the frame at --at as the poster / frame 0")
    o.add_argument("video"); o.add_argument("--at", type=float, required=True)
    o.set_defaults(fn=cmd_poster)

    k = sub.add_parser("make", help="record + compose + check + render (+ poster) in one call")
    k.add_argument("scenario"); k.add_argument("plan"); k.add_argument("--out", required=True)
    src = k.add_mutually_exclusive_group()
    src.add_argument("--base-url", help="override CONFIG['base_url'] (app already running)")
    src.add_argument("--serve", help="serve this static directory on a random local port and record it")
    k.add_argument("--name", default="video", help="output file name (default video → OUT/video.mp4)")
    k.add_argument("--scale", type=float); k.add_argument("--fps", type=int, default=60)
    k.add_argument("--quality", default="delivery"); k.add_argument("--poster-at", type=float)
    k.add_argument("--skip-render", action="store_true"); k.add_argument("--no-check", action="store_true")
    k.set_defaults(fn=cmd_make)

    d = sub.add_parser("demo", help="record + compose + render the bundled demo app")
    d.add_argument("--out", default="out/demo"); d.add_argument("--scale", type=float, default=2)
    d.add_argument("--fps", type=int, default=60); d.add_argument("--quality", default="delivery")
    d.add_argument("--poster-at", type=float, default=9.0); d.add_argument("--skip-render", action="store_true")
    d.add_argument("--examples", help="path to an examples/ directory")
    d.set_defaults(fn=cmd_demo)

    h = sub.add_parser("doctor", help="check Python, Chromium, ffmpeg and Node 22+")
    h.set_defaults(fn=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    global JSON
    a = build_parser().parse_args(argv)
    JSON = a.json
    try:
        res, code, err = a.fn(a), 0, None
    except Fail as e:
        res, code, err = e.extra, e.code, str(e)
    except SystemExit as e:  # e.g. render._npx() when Node is missing
        if isinstance(e.code, int) or e.code is None:
            raise
        res, code, err = {}, 2, str(e.code)
    if JSON:
        print(json.dumps({"ok": code == 0, "command": a.cmd, **({"error": err} if err else {}), **(res or {})}, ensure_ascii=False))
    elif err:
        print(f"error: {err}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
