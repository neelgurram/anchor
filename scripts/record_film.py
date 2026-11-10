"""Render the deck's cinematic brain clips frame by frame (smooth and repeatable), then encode mp4.

Needs the API (8030) and Vite (5180) running. Uses frontend/film.html, which reads the same real
patient data as the app (RESECT Case12, seed 9).

    python scripts/record_film.py                       # all scenes -> demo/film_<scene>.mp4 (+ poster png)
    python scripts/record_film.py hero shift            # some scenes
    python scripts/record_film.py --stills 0 3 6 hero   # just a few frames to look at (scratch folder)
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import tempfile

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
URL = "http://localhost:5180/film.html?scene={scene}&capture=1"
SCENES = ["hero", "shift", "bad", "fix"]
POSTER_AT = {"hero": 1.0, "shift": 6.5, "bad": 6.5, "fix": 6.8}
W, H, FPS = 1920, 1080, 30


def open_scene(b, scene):
    pg = b.new_page(viewport={"width": W, "height": H})
    pg.goto(URL.format(scene=scene))
    pg.wait_for_selector("#film-ready", state="attached", timeout=180_000)
    pg.wait_for_function("() => typeof window.__render === 'function'", timeout=60_000)
    pg.evaluate("document.fonts.ready")
    return pg


def shot(pg, t, path):
    pg.evaluate(f"window.__render({t})")
    pg.screenshot(path=str(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes", nargs="*", default=SCENES)
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--out", default=str(ROOT / "demo"))
    a = ap.parse_args()
    scenes = [s for s in a.scenes if s in SCENES] or SCENES
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for scene in scenes:
            pg = open_scene(b, scene)
            dur = pg.evaluate("window.__duration")
            shot(pg, 0.0, out / "_warm.png")                     # first render compiles shaders
            if a.stills is not None:
                for t in a.stills:
                    shot(pg, t, out / f"still_{scene}_{t:04.1f}.png")
                    print("still", scene, t)
                pg.close()
                continue
            tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"film_{scene}_"))
            n = int(round(dur * FPS))
            for i in range(n):
                shot(pg, i / FPS, tmp / f"f{i:05d}.png")
                if i % 60 == 0:
                    print(f"{scene}: frame {i}/{n}", flush=True)
            shot(pg, POSTER_AT[scene], out / f"film_{scene}.png")
            pg.close()
            mp4 = out / f"film_{scene}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "f%05d.png"),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow",
                            "-movflags", "+faststart", str(mp4)], check=True)
            shutil.rmtree(tmp)
            print("wrote", mp4)
        b.close()
    (out / "_warm.png").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
