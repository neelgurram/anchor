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


def main():
    DEMO.mkdir(exist_ok=True)
    shutil.rmtree(RAW, ignore_errors=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(RAW),
                            record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        click = lambda name: page.get_by_role("button", name=name, exact=False).first.click()
        wait = lambda s: page.wait_for_timeout(int(s * 1000))

        # warm the solver cache so QAOA's live run isn't the slow part of the take
        page.request.post("http://localhost:8030/api/health")
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
        click("Show circuit"); wait(9)                     # beat 9: the circuit and what it costs on Heron
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
