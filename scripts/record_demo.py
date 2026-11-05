"""Record the ~2-minute demo video with a scripted, repeatable browser run.

    python scripts/record_demo.py            # needs API on 8030 and vite on 5180
    -> demo/anchor_demo.mp4 (silent; voiceover is added afterwards, see demo/VOICEOVER.md)

Every beat waits long enough for its voiceover line. The numbers on screen are live API values.
"""
import pathlib
import shutil
import subprocess
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
RAW = DEMO / "_raw"
URL = "http://localhost:5180/"
W, H = 1600, 900


API = "http://localhost:8030"
DEMO_PROBLEM = {"case_id": "Case12", "n_used": 8, "k": 2, "outlier_rate": 0.3, "seed": 9}


def warm_cache():
    """Solve the demo patient once BEFORE recording, without the browser's software renderer
    competing for CPU. The app then shows these real results and their real compute times."""
    import json
    import urllib.request

    def post(path, body):
        req = urllib.request.Request(API + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())

    pid = post("/api/problem", DEMO_PROBLEM)["problem_id"]
    with urllib.request.urlopen(f"{API}/api/circuit/{pid}?p=1", timeout=300) as r:
        r.read()
    for s in ["naive", "qaoa", "danneal"]:
        r = post("/api/solve", {"problem_id": pid, "solver": s, "params": {}})
        print(f"warm {s}: map error {r['evaluation']['tre']:.2f} mm, {r['result']['wall_time']:.1f} s")


def main():
    DEMO.mkdir(exist_ok=True)
    warm_cache()
    shutil.rmtree(RAW, ignore_errors=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(RAW),
                            record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        click = lambda name: page.get_by_role("button", name=name, exact=False).first.click()
        wait = lambda s: page.wait_for_timeout(int(s * 1000))

        page.goto(URL)
        wait(4)                                            # beat 1: title, the problem
        click("Load patient"); wait(6)                     # beat 2: real patient, MRI landmarks
        click("Open the skull"); wait(8)                   # beat 3: brain sags; map off by X mm
        click("Take ultrasound"); wait(7)                  # beat 4: candidate matches, some wrong
        click("Naive"); wait(4)
        click("Correct the map"); wait(8)                  # beat 5: naive bends the map
        click("QAOA"); wait(18)                            # beat 6: sampled answers flash, settle
        click("Correct the map"); wait(8)                  # beat 7: map snaps back, error in mm
        click("Digitized anneal"); wait(10)
        click("Correct the map"); wait(6)                  # beat 8: annealing-style schedule agrees
        page.get_by_role("button", name="Solver lab").click(); wait(2)
        click("Show circuit"); wait(3)                     # beat 9: the circuit and what it costs on Heron
        for _ in range(4):
            page.locator(".circuit").evaluate("el => el.scrollBy({left: 600, behavior: 'smooth'})"); wait(1.6)
        page.get_by_role("button", name="Results").click(); wait(5)
        for _ in range(6):                                 # beat 10: the honest benchmark
            page.mouse.wheel(0, 520); wait(3)
        wait(3)
        ctx.close()
        b.close()

    webm = next(RAW.glob("*.webm"))
    out = DEMO / "anchor_demo.mp4"
    ff = shutil.which("ffmpeg")
    if not ff:
        shutil.move(webm, DEMO / "anchor_demo.webm")
        print("ffmpeg not found; saved", DEMO / "anchor_demo.webm")
        return
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", "-preset", "slow", "-movflags", "+faststart", str(out)], check=True)
    shutil.rmtree(RAW, ignore_errors=True)
    print("saved", out)


if __name__ == "__main__":
    sys.exit(main())
