"""Turn footage + a plan into a HyperFrames composition directory.

A plan is a Python module with ``def plan(ctx) -> dict``. ``ctx`` exposes the footage: ``ctx.marks``
(name -> seconds), ``ctx.boxes`` (name -> {x, y, w, h} in CSS px), ``ctx.duration`` and helpers
``ctx.m(name, default)``, ``ctx.center(box_name, dx, dy)``. All plan times are **footage seconds**
unless stated; the composer converts them to composition time.

Plan keys (all optional except ``camera``):
  title, lang, video_start, media_start, video_end, cursor_end,
  intro {title, subtitle, duration}, outro {title | logo, line, duration, overlap, subtitle},
  camera [{from, zoom, focus: "cursor" | "center" | [x, y]}],
  subtitles [[start, end, text]], callouts [{at, until, html, x, y, side}], halos [{at, box, pad}],
  sfx [{at, file, volume}], key_sfx {files, max, volume}, click_sfx {file, volume},
  music {file, volume, fade_in, fade_out}, tag (small label at the top), look {...css tokens...},
  canvas {width, height}, padding (fraction of width), fps.
"""
from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .capture import load_module

PKG = Path(__file__).resolve().parent
WORDS_PER_SECOND_FLOOR = 0.3   # seconds per word a subtitle must stay readable

LOOK_PRESETS = {
    "violet": None,   # the stylesheet default
    "mint": "radial-gradient(900px 620px at 16% 20%, rgba(45,130,81,0.42), transparent 66%), radial-gradient(800px 560px at 84% 80%, rgba(84,68,230,0.26), transparent 62%), linear-gradient(135deg, #DFF5EA 0%, #EEF4F1 50%, #DCEBFF 100%)",
    "sunset": "radial-gradient(900px 620px at 18% 22%, rgba(255,120,80,0.45), transparent 66%), radial-gradient(800px 560px at 82% 78%, rgba(255,200,80,0.40), transparent 62%), linear-gradient(135deg, #FFE6DC 0%, #FFF1E6 50%, #FDE2F3 100%)",
    "graphite": "radial-gradient(900px 620px at 16% 20%, rgba(255,255,255,0.10), transparent 66%), radial-gradient(800px 560px at 84% 80%, rgba(84,68,230,0.35), transparent 62%), linear-gradient(135deg, #2A2A3A 0%, #1E1E2A 50%, #262636 100%)",
    "ocean": "radial-gradient(900px 620px at 14% 18%, rgba(30,120,255,0.45), transparent 66%), radial-gradient(820px 560px at 86% 82%, rgba(60,220,200,0.40), transparent 62%), radial-gradient(700px 520px at 78% 12%, rgba(130,90,255,0.35), transparent 60%), linear-gradient(135deg, #DCE8FF 0%, #E6F2FF 48%, #D9F7F2 100%)",
}


@dataclass
class Ctx:
    marks: dict[str, float]
    boxes: dict[str, dict[str, float]]
    duration: float
    meta: dict[str, Any] = field(default_factory=dict)

    def m(self, name: str, default: float | None = None) -> float:
        if name in self.marks:
            return self.marks[name]
        if default is None:
            raise KeyError(f"mark {name!r} not in footage; have {sorted(self.marks)}")
        return default

    def center(self, name: str, dx: float = 0, dy: float = 0) -> list[float]:
        b = self.boxes[name]
        return [b["x"] + b["w"] / 2 + dx, b["y"] + b["h"] / 2 + dy]

    def box(self, name: str) -> dict[str, float]:
        return self.boxes[name]


def load_footage(footage_dir: Path) -> tuple[dict, Ctx]:
    meta = json.loads((Path(footage_dir) / "events.json").read_text())
    marks: dict[str, float] = {}
    boxes: dict[str, dict[str, float]] = {}
    for e in meta["events"]:
        if e["type"] == "mark":
            marks[e["name"]] = e["t"]
        elif e["type"] in ("scroll_start", "scroll_end"):
            marks[e["type"]] = e["t"]
        elif e["type"] == "box":
            boxes[e["name"]] = {"x": e["x"], "y": e["y"], "w": e["w"], "h": e["h"]}
    return meta, Ctx(marks=marks, boxes=boxes, duration=meta["duration"], meta=meta)


def _css_vars(look: dict, stage: dict, fx_scale: float) -> str:
    vars_ = {
        "--sc-stage-x": f"{stage['x']}px", "--sc-stage-y": f"{stage['y']}px",
        "--sc-stage-w": f"{stage['w']}px", "--sc-stage-h": f"{stage['h']}px", "--sc-fx-scale": f"{fx_scale:.5f}",
    }
    wp = look.get("wallpaper")
    if wp in LOOK_PRESETS and LOOK_PRESETS[wp]:
        vars_["--sc-wallpaper"] = LOOK_PRESETS[wp]
    elif wp and wp not in LOOK_PRESETS:
        vars_["--sc-wallpaper"] = wp
    for key, var in (("accent", "--sc-accent"), ("accent_dark", "--sc-accent-dark"), ("accent_soft", "--sc-accent-soft"),
                     ("text", "--sc-text"), ("text_2", "--sc-text-2"), ("border", "--sc-border"), ("surface", "--sc-surface"),
                     ("font", "--sc-font")):
        if look.get(key):
            vars_[var] = look[key]
    if look.get("radius") is not None:
        vars_["--sc-radius"] = f"{look['radius']}px"
    if look.get("cursor_size"):
        vars_["--sc-cursor"] = f"{look['cursor_size']}px"
    return " ".join(f"{k}: {v};" for k, v in vars_.items())


def _copy_media(src: str | Path, out: Path, sub: str = "assets/media") -> str:
    src = Path(src)
    dst = out / sub / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    return f"{sub}/{src.name}"


def compose(plan_path: Path, footage_dir: Path, out_dir: Path, *, log=print) -> dict:
    """Write ``out_dir/`` (index.html, assets/, footage/) and return the resolved plan."""
    footage_dir, out_dir = Path(footage_dir), Path(out_dir)
    meta, ctx = load_footage(footage_dir)
    plan = load_module(Path(plan_path), "plan").plan(ctx)

    canvas = plan.get("canvas") or {"width": 1920, "height": 1080}
    W, H = canvas["width"], canvas["height"]
    pad = plan.get("padding", 0.05)
    cw, ch = meta["css_viewport"]["width"], meta["css_viewport"]["height"]
    sw = round(W * (1 - 2 * pad)); sh = round(sw * ch / cw)
    stage = {"x": round((W - sw) / 2), "y": round((H - sh) / 2), "w": sw, "h": sh}
    fx_scale = sw / cw

    intro = plan.get("intro")
    V0 = round(plan.get("video_start", (intro["duration"] - 0.4) if intro else 0.0), 3)
    MS = round(plan.get("media_start", ctx.m("hook", 0.0) + 0.15), 3)
    VE = min(ctx.duration, plan.get("video_end", ctx.m("end", ctx.duration) + 0.1))
    VD = round(VE - MS, 3)
    toC = lambda tf: round(V0 + (tf - MS), 3)
    outro = plan.get("outro")
    if outro:
        O = round(V0 + VD - outro.get("overlap", 0.45), 3)
        D = round(O + outro.get("duration", 3.4), 3)
        outro = {**outro, "start": O, "duration": outro.get("duration", 3.4)}
    else:
        O, D = None, round(V0 + VD, 3)

    # ---- camera: resolve focus boxes to points, keep footage time ----
    camera = []
    for seg in plan["camera"]:
        f = seg.get("focus", "center")
        if isinstance(f, str) and f not in ("cursor", "center"):
            f = ctx.center(f)
        camera.append({"from": float(seg["from"]), "zoom": float(seg.get("zoom", 1.0)), "focus": f})

    # ---- subtitles (footage time -> comp time), reading-floor check ----
    subs = []
    for start, end, text in plan.get("subtitles", []):
        a, b = toC(start), toC(end)
        need = WORDS_PER_SECOND_FLOOR * len(text.split())
        if b - a < need:
            log(f"  subtitle short by {need - (b - a):.1f}s: {text!r}")
        subs.append([a, b, text])
    if outro and outro.get("subtitle"):
        subs.append([O + 0.45, D - 0.2, outro["subtitle"]])
    for i in range(1, len(subs)):
        if subs[i][0] < subs[i - 1][1] - 0.05:
            log(f"  subtitles overlap: {subs[i-1][2]!r} / {subs[i][2]!r}")

    halos = []
    for h in plan.get("halos", []):
        b = ctx.box(h["box"]) if isinstance(h["box"], str) else h["box"]
        halos.append({"at": h["at"], "box": b, "pad": h.get("pad", 10)})

    # ---- audio ----
    audio = []
    def audio_tag(id_, src, start, vol, extra=""):
        audio.append(f'<audio id="{id_}" src="{src}" data-start="{start:.2f}" data-track-index="{10 + len(audio)}" data-volume="{vol}"{extra}></audio>')
    music = plan.get("music")
    if music:
        src = _copy_media(music["file"], out_dir)
        fi, fo, v = music.get("fade_in", 0.6), music.get("fade_out", 1.8), music.get("volume", 0.3)
        lane = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": 0, "v": 0}, {"t": fi, "v": 1}, {"t": round(D - fo, 2), "v": 1}, {"t": round(D, 2), "v": 0}]}]})
        audio_tag("sc-music", src, 0.0, v, f" data-duration=\"{D}\" data-automation='{lane}'")
    keys = [e["t"] for e in meta["events"] if e["type"] == "key"]
    ks = plan.get("key_sfx")
    if ks and keys:
        files = ks["files"]; mx = ks.get("max", 6); step = max(1, len(keys) // mx)
        for i, t in enumerate(keys[::step][:mx]):
            audio_tag(f"sc-key-{i+1}", _copy_media(files[i % len(files)], out_dir), toC(t), ks.get("volume", 0.35))
    cs = plan.get("click_sfx")
    if cs:
        for i, e in enumerate([e for e in meta["events"] if e["type"] == "down"]):
            audio_tag(f"sc-click-{i+1}", _copy_media(cs["file"], out_dir), toC(e["t"]), cs.get("volume", 0.75))
    for i, s in enumerate(plan.get("sfx", [])):
        at = s["at"] if not s.get("comp_time") else None
        audio_tag(f"sc-sfx-{i+1}", _copy_media(s["file"], out_dir), toC(s["at"]) if at is not None else s["at"], s.get("volume", 0.6))
    if outro and outro.get("sfx"):
        audio_tag("sc-outro-sfx", _copy_media(outro["sfx"], out_dir), O + 0.05, outro.get("sfx_volume", 0.7))

    # ---- title cards ----
    intro_html = outro_html = ""
    if intro:
        intro_html = (f'<section id="sc-intro" class="clip sc-card" data-start="0" data-duration="{intro["duration"]}" data-track-index="5">'
                      f'<div class="t1">{intro["title"]}</div>' + (f'<div class="t2">{html.escape(intro["subtitle"])}</div>' if intro.get("subtitle") else "") + "</section>")
    if outro:
        if outro.get("logo"):
            mark = f'<img src="{_copy_media(outro["logo"], out_dir)}" alt="" />'
        else:
            mark = f'<span>{html.escape(outro.get("title", ""))}</span>'
        outro_html = (f'<section id="sc-outro" class="clip sc-card" data-start="{O}" data-duration="{outro["duration"]}" data-track-index="5">'
                      f'<div class="mark">{mark}</div>' + (f'<div class="line">{html.escape(outro["line"])}</div>' if outro.get("line") else "") + "</section>")
    tag_html = f'<div id="sc-tag"><i></i>{html.escape(plan["tag"])}</div>' if plan.get("tag") else ""

    look = dict(plan.get("look", {}))
    sc = {
        "canvas": {"width": W, "height": H}, "stage": stage, "video_start": V0, "media_start": MS, "video_end": VE,
        "cursor_end": plan.get("cursor_end", ctx.m("end", ctx.duration) - 0.05), "camera": camera, "subtitles": subs,
        "callouts": plan.get("callouts", []), "halos": halos, "intro": intro, "outro": outro,
        "look": {"focus_omega": look.get("focus_omega", 5.2), "zoom_omega": look.get("zoom_omega", 4.2), "ring_radius": look.get("ring_radius", 54)},
    }

    # ---- write project ----
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    (out_dir / "footage").mkdir(exist_ok=True)
    shutil.copy2(PKG / "assets" / "studio.js", out_dir / "assets" / "studio.js")
    shutil.copy2(PKG / "assets" / "studio.css", out_dir / "assets" / "studio.css")
    take_src, take_dst = footage_dir / "take.mp4", out_dir / "footage" / "take.mp4"
    if not take_dst.exists() or take_dst.stat().st_mtime < take_src.stat().st_mtime:
        shutil.copy2(take_src, take_dst)
    (out_dir / "footage" / "events.js").write_text("window.TAKE = " + json.dumps(meta, ensure_ascii=False) + ";\n")
    (out_dir / "hyperframes.json").write_text(json.dumps({
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "media": {"autoProxy": True},
    }, indent=2))
    tpl = (PKG / "templates" / "index.html").read_text()
    repl = {
        "@@LANG@@": plan.get("lang", "en"), "@@TITLE@@": html.escape(plan.get("title", "screencraft video")),
        "@@W@@": str(W), "@@H@@": str(H), "@@FW@@": str(cw), "@@FH@@": str(ch), "@@D@@": str(D), "@@FPS@@": str(plan.get("fps", 60)),
        "@@V0@@": str(V0), "@@VD@@": str(VD), "@@MS@@": str(round(MS, 3)),
        "@@CSS_VARS@@": _css_vars(look, stage, fx_scale), "@@EXTRA_CSS@@": plan.get("extra_css", ""),
        "@@INTRO@@": intro_html, "@@OUTRO@@": outro_html, "@@TAG@@": tag_html, "@@AUDIO@@": "\n      ".join(audio),
        "@@SC_JSON@@": json.dumps(sc, ensure_ascii=False),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    (out_dir / "index.html").write_text(tpl)
    log(f"composition: {out_dir / 'index.html'}  (video {V0}s→{round(V0 + VD, 2)}s, total {D}s, {len(subs)} subtitles, {len(audio)} audio clips)")
    return {"duration": D, "video_start": V0, "media_start": MS, "video_duration": VD, "outro_start": O, "sc": sc}
