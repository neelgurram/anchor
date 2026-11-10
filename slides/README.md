# Slides

18 slides for a 5-minute talk. Each slide has 2–4 sentences, and the speaker notes hold the extra detail and likely judge questions.

- **Live deck:** https://claude.ai/artifact/RJCmhfx3aNvt32uLrt2xVM. It is private until it is shared from its Share menu. Export it to PDF or PowerPoint from Share › Export, and put the export in this folder for the submission.
- **Source:** `source/`, with one HTML file per slide and the order in `deck.json`.

## Rubric coverage

Weights come from the official statewide rubric (scored 1–5, plus a hardware bonus). Section numbers come from the Miami-Dade judging criteria (scored 1–10).

| Rubric item | Weight | Slides |
|---|---|---|
| 01 Problem definition & relevance | 15% | 2 The problem (who it affects, 2 cm shift) · 3 Why it's hard (today's options, one bad match bends the map) |
| 02 Quantum rationale & potential | 20% | 5 Max clique as a QUBO · 6 Why quantum, honestly (no speed-up claimed) · 14 When would quantum win (scale and error rates needed) |
| 03 Technical implementation (Qiskit) | 20% | 7 Built in Qiskit (circuits, hybrid loop, transpiler, primitives, error suppression, tests) · 8 The app |
| 04 Results & validation | 10% | 9 Benchmark vs classical baselines with 95% CIs · 10 Confidence alarm tested on held-out patients · 11–12 simulator vs noise model vs hardware · 13 classical vs logic gates vs annealing on the same instances |
| 05 Innovation & creativity | 10% | 15 What makes Anchor different · 10 the self-check |
| 06 Presentation & communication | 15% | One idea per slide, party analogy (5), one-sentence close (18), the demo video |
| 07 Q&A, teamwork & learning journey | 10% | 17 Built solo by Neel Gurram, biggest lesson, next month · likely questions in the notes on 18 |
| Hardware bonus, top tier (+5) | +5 | 11 Real IBM hardware · 12 Noise analysis (compared to the simulator, noise analysed, error suppression applied) |
| Required limitations | — | 16 Limitations (full list in LIMITATIONS.md) |

## Before presenting
- Solo project: Neel Gurram is on slide 1, and slide 17 lists what he built.
- D-Wave needs paid or approved access, so it is not in the deck. If it ever runs, `python scripts/compare_paradigms.py` adds it to the comparison; then update slides 13, 16 and 17.
- Slide 8 plays `demo/anchor_demo_slide.mp4` (20 s) by itself, looping. Submit `demo/anchor_demo_short.mp4` (45 s) as the demo video.
