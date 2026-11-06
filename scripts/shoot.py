"""Drive the Surgery flow in headless Chromium and save a screenshot per step.

Usage: python scripts/shoot.py [out_dir]   (needs the API on 8030 and vite on 5180)
"""
import sys, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "results/screens")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:5180/"


def btn(page, text):
    page.get_by_role("button", name=text, exact=False).first.click()


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    page = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_timeout(2500)
    page.screenshot(path=OUT / "0_start.png")
    btn(page, "Load patient"); page.wait_for_timeout(3000); page.screenshot(path=OUT / "1_load.png")
    btn(page, "Open the skull"); page.wait_for_timeout(3500); page.screenshot(path=OUT / "2_skull.png")
    btn(page, "Take ultrasound"); page.wait_for_timeout(2500); page.screenshot(path=OUT / "3_ultrasound.png")
    btn(page, "Naive"); page.wait_for_timeout(2500); page.screenshot(path=OUT / "4_naive_pick.png")
    btn(page, "Correct the map"); page.wait_for_timeout(3500); page.screenshot(path=OUT / "5_naive_map.png")
    btn(page, "QAOA"); page.wait_for_timeout(16000); page.screenshot(path=OUT / "6_qaoa_pick.png")
    btn(page, "Correct the map"); page.wait_for_timeout(3500); page.screenshot(path=OUT / "7_qaoa_map.png")
    btn(page, "Real error"); page.wait_for_timeout(1500); page.screenshot(path=OUT / "8_qaoa_real_error.png")
    page.get_by_role("button", name="Results").click(); page.wait_for_timeout(2500)
    page.get_by_text("Does the confidence map tell the truth?").scroll_into_view_if_needed()
    page.wait_for_timeout(1500); page.screenshot(path=OUT / "9_results_confidence.png")
    print("console errors:", errors)
    b.close()
