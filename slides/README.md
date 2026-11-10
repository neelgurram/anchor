# Slides

18 slides for a 5-minute talk. Each slide has 2–4 sentences, and the speaker notes hold the extra detail and likely judge questions.

- **Live deck:** https://claude.ai/artifact/RJCmhfx3aNvt32uLrt2xVM. It is private until it is shared from its Share menu. Export it to PDF or PowerPoint from Share › Export, and put the export in this folder for the submission.
- **Source:** `source/`, with one HTML file per slide and the order in `deck.json`.

## Story

The deck is in five parts, and each slide has one idea:

1. **The problem (slides 1–5):** the surgeon's map is the pre-operative MRI; the brain moves; ultrasound can measure how far it moved; one wrong match ruins the fix.
2. **Our solution (6):** Anchor throws out the wrong matches, fixes the map, and checks the fix.
3. **How it works (7–10):** correct matches agree; finding them is a quantum puzzle; built in Qiskit; the app.
4. **Results (11–14):** 22 real patients, the self-check, the real IBM chip, three kinds of solver.
5. **What's next (15–18):** what quantum needs to win, what's new and missing, about me, close.

## Rubric coverage

Weights come from the official statewide rubric (scored 1–5, plus a hardware bonus). Section numbers come from the Miami-Dade judging criteria (scored 1–10).

| Rubric item | Weight | Slides |
|---|---|---|
| 01 Problem definition & relevance | 15% | 2 The MRI map · 3 The brain moves (2 cm) · 4 Ultrasound matches · 5 One wrong match ruins the fix |
| 02 Quantum rationale & potential | 20% | 7 Correct matches agree · 8 Max clique as a QUBO, why quantum · 15 What quantum needs (scale and error rates) |
| 03 Technical implementation (Qiskit) | 20% | 9 Built in Qiskit (circuits, hybrid loop, transpiler, primitives, error suppression, tests) · 10 The app |
| 04 Results & validation | 10% | 11 Benchmark on 22 RESECT patients vs classical baselines · 12 Confidence alarm · 13 Real IBM hardware vs simulator and noise model · 14 Classical vs logic gates vs annealing |
| 05 Innovation & creativity | 10% | 16 What's new · 12 the self-check |
| 06 Presentation & communication | 15% | Problem → solution → how → results → next; party analogy (8); one-sentence close (18); the demo video |
| 07 Q&A, teamwork & learning journey | 10% | 17 Built solo by Neel Gurram, what he learned, what's next · likely questions in the notes on 18 |
| Hardware bonus, top tier (+5) | +5 | 13 Real IBM hardware, compared to the simulator, noise analysed, error suppression applied (detail in its speaker notes) |
| Required limitations | — | 16 What's missing (full list in LIMITATIONS.md) |

## Before presenting
- Solo project: Neel Gurram is on slide 1, and slide 17 lists what he built.
- D-Wave needs paid or approved access, so it is not in the deck. If it ever runs, `python scripts/compare_paradigms.py` adds it to the comparison; then update slides 14 and 16.
- Slide 10 plays `demo/anchor_demo_slide.mp4` (20 s) by itself, looping. Submit `demo/anchor_demo_short.mp4` (45 s) as the demo video.
