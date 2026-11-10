"""Cut demo/anchor_demo.mp4 down to the moments where something happens.

    python scripts/cut_demo.py            -> demo/anchor_demo_short.mp4  (45 s, the submitted demo)
    python scripts/cut_demo.py slides     -> demo/anchor_demo_slide.mp4  (about 20 s, plays inside slide 8)

Segment times are in seconds of the full recording; re-check them if the recording changes.
"""
import pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "demo" / "anchor_demo.mp4"
SHORT = [            # (start, end, what happens)
    (7.0, 12.0, "brain loads, camera flies in, MRI landmarks"),
    (13.0, 18.0, "skull opens, brain sags, map 19.6 mm off"),
    (20.5, 25.0, "ultrasound candidates appear"),
    (29.5, 38.0, "trust every match: map bends red, alarm fires"),
    (42.5, 47.0, "QAOA: sampled answers flash"),
    (58.5, 64.5, "map snaps back: 1.6 mm, trusted"),
    (67.5, 71.5, "real error on hidden expert points"),
    (74.5, 84.0, "IBM ibm_fez answers replayed: same map, job ID"),
]
SLIDE = [               # the bare story: stale map, bad fix + alarm, quantum fix, real hardware
    (13.0, 16.5, "skull opens, map 19.6 mm off"),
    (32.5, 36.5, "trust every match: map bends red, alarm fires"),
    (42.5, 45.5, "QAOA: sampled answers flash"),
    (58.5, 63.0, "map snaps back: 1.6 mm, trusted"),
    (75.0, 81.5, "IBM ibm_fez answers replayed: same map"),
]
slides = len(sys.argv) > 1 and sys.argv[1] == "slides"
SEGMENTS = SLIDE if slides else SHORT
OUT = ROOT / "demo" / ("anchor_demo_slide.mp4" if slides else "anchor_demo_short.mp4")
FADE = 0.3

parts, chains, offset, prev = [], [], 0.0, "v0"
for i, (a, b, _) in enumerate(SEGMENTS):
    parts.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=25[v{i}]")
for i in range(1, len(SEGMENTS)):
    offset += (SEGMENTS[i - 1][1] - SEGMENTS[i - 1][0]) - FADE
    out = f"x{i}" if i < len(SEGMENTS) - 1 else "vout"
    chains.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[{out}]")
    prev = out
last = SEGMENTS[-1][1] - SEGMENTS[-1][0]
fg = ";".join(parts + chains) + f";[vout]fade=t=out:st={offset + last - 0.6:.3f}:d=0.6[final]"
subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-i", str(SRC), "-filter_complex", fg,
                "-map", "[final]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow",
                "-movflags", "+faststart", str(OUT)], check=True)
t = 0.0
for i, (a, b, what) in enumerate(SEGMENTS):
    print(f"{t:5.1f}s  {what}")
    t += (b - a) - FADE
print("saved", OUT)
