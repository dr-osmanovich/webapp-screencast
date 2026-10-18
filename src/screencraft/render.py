"""Thin wrappers around the HyperFrames CLI (``npx hyperframes``) and ffmpeg for posters."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _npx() -> list[str]:
    if shutil.which("npx") is None:
        raise SystemExit("npx not found: install Node.js 20+ (HyperFrames renders through it).")
    return ["npx", "--yes", "hyperframes"]


def check(composition_dir: Path) -> int:
    """Run ``hyperframes check`` (lint + layout + contrast). Returns the exit code."""
    return subprocess.run(_npx() + ["check"], cwd=composition_dir).returncode


def render(composition_dir: Path, out: Path, *, fps: int = 60, quality: str = "delivery",
           frames_cache_dir: Path | None = None, extra: list[str] | None = None) -> int:
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = _npx() + ["render", "--fps", str(fps), "--quality", quality, "--video-frame-format", "png", "--output", str(out)]
    if frames_cache_dir:
        cmd += ["--frames-cache-dir", str(Path(frames_cache_dir).resolve())]
    if extra:
        cmd += extra
    env = dict(os.environ)
    return subprocess.run(cmd, cwd=composition_dir, env=env).returncode


def snapshot(composition_dir: Path, at: list[float], out: Path) -> int:
    cmd = _npx() + ["snapshot", "--at", ",".join(f"{t:g}" for t in at), "--no-end", "-o", str(Path(out).resolve())]
    return subprocess.run(cmd, cwd=composition_dir).returncode


def bake_poster(video: Path, at: float, *, jpg: Path | None = None, crf: int = 16) -> Path:
    """Pick the frame at ``at`` seconds as the poster and bake it as frame 0 of the video.

    Keeps the untouched render next to it as ``<name>.raw.mp4`` and writes ``<name>.jpg``.
    """
    video = Path(video)
    raw = video.with_suffix(".raw.mp4")
    jpg = Path(jpg) if jpg else video.with_suffix(".jpg")
    if not raw.exists():
        shutil.copy2(video, raw)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(at), "-i", str(raw), "-frames:v", "1", "-q:v", "2", str(jpg)], check=True)
    tmp = video.with_suffix(".poster.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-i", str(jpg),
                    "-filter_complex", "[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]",
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)
    return jpg
