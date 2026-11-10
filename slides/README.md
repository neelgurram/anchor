# Slides

17 slides for a 5-minute talk. Each slide has 2–4 sentences, and the speaker notes hold the extra detail and likely judge questions.

- **Live deck:** https://claude.ai/artifact/RJCmhfx3aNvt32uLrt2xVM. It is private until it is shared from its Share menu. Export it to PDF or PowerPoint from Share › Export, and put the export in this folder for the submission.
- **Source:** `source/`, with one HTML file per slide and the order in `deck.json`.

## Story

The deck is in five parts, and each slide has one idea:

1. **The problem (slides 1–3):** the surgeon's map is the pre-operative MRI and it goes out of date when the brain shifts; ultrasound can update it, but one wrong match ruins the fix.
2. **Our solution (4–7):** the three steps; correct matches agree; finding them is a quantum puzzle; fixing the map and checking the fix.
3. **How we built it (8–9):** Qiskit and the app.
4. **Results (10–13):** 22 real patients, the self-check, the real IBM chip, three kinds of solver.
5. **What's next (14–17):** what quantum needs to win, what's new and missing, about me, close.

## Rubric coverage

Weights come from the official statewide rubric (scored 1–5, plus a hardware bonus). Section numbers come from the Miami-Dade judging criteria (scored 1–10).

| Rubric item | Weight | Slides |
|---|---|---|
| 01 Problem definition & relevance | 15% | 2 The map goes out of date (pre-op MRI, navigation, 2 cm shift; who it hurts: patients, surgeons, hospitals without an operating-room MRI) · 3 One wrong ultrasound match ruins the fix |
| 02 Quantum rationale & potential | 20% | 4 The three steps · 5 Correct matches agree · 6 Max clique as a QUBO; names superposition and sampling (needed for 3+); says a normal computer is still faster · 14 What quantum needs (scale and error rates) |
| 03 Technical implementation (Qiskit) | 20% | 8 Built in Qiskit: parameterized circuits, Sampler primitive, transpiler (the 4 descriptor), hybrid workflow and error suppression (the 5 descriptor's examples), 39 tests · 9 The app · 7 the fix and self-check |
| 04 Results & validation | 10% | 10 Benchmark: 264 tests on 22 RESECT patients vs classical baselines, 95% error bars · 11 Confidence alarm · 12 Real IBM hardware vs simulator and noise model · 13 Classical vs logic gates vs annealing |
| 05 Innovation & creativity | 10% | 15 What's new · 7 and 11 the self-check |
| 06 Presentation & communication | 15% | Problem → solution → how we built it → results → next; party analogy (6); one-sentence close (17); the demo video |
| 07 Q&A, teamwork & learning journey | 10% | 16 Built solo by Neel Gurram, what he learned, what's next · likely questions in the notes on 17 |
| Hardware bonus, top tier (+5) | +5 | 12 Real IBM hardware (+3 tier) plus all three +5 conditions shown as labels on the slide: compared to a perfect simulator, noise analysed with a noisy-chip model, error suppression applied (dynamical decoupling and twirling). The rubric needs only one of the three. Have the job IDs ready if a judge asks. |
| Required limitations | — | 15 What's missing (full list in LIMITATIONS.md) |

## Before presenting
- Solo project: Neel Gurram is on slide 1, and slide 16 lists what he built.
- D-Wave needs paid or approved access, so it is not in the deck. If it ever runs, `python scripts/compare_paradigms.py` adds it to the comparison; then update slides 13 and 15.
- Slide 9 plays `demo/anchor_demo_slide.mp4` (20 s) by itself, looping. Submit `demo/anchor_demo_short.mp4` (45 s) as the demo video.
