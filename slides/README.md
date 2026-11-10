# Slides

11 slides for a 5-minute talk. Each slide shows one idea in one or two short lines plus a picture. Each slide's speaker notes start with **SAY:**, a script of about 50 words (about 4 minutes in total, including the 20-second demo clip). After that, **IF ASKED:** holds the detail and likely judge questions.

- **Live deck:** https://claude.ai/artifact/RJCmhfx3aNvt32uLrt2xVM. It is private until it is shared from its Share menu. Export it to PDF or PowerPoint from Share › Export, and put the export in this folder for the submission.
- **Source:** `source/`, with one HTML file per slide and the order in `deck.json`. PNG renders are in `previews/`.

## Story

1. **The problem (slides 1–3):** surgeons steer by a pre-op MRI that goes out of date when the brain shifts; ultrasound can update it, but some matches are wrong.
2. **Our solution (4–5):** Anchor keeps only the matches that agree; picking them is a quantum puzzle.
3. **Results (6–9):** what Anchor looks like on one real patient (19.6 → 16.5 → 1.6 mm); the app; 22 real patients; Qiskit and the real IBM chip.
4. **What's next (10–11):** what quantum needs to win, next month, a one-sentence close.

The pictures on slides 2–6 are simple drawings with one consistent key:

| Mark | Meaning |
|---|---|
| Dashed outline | The surgeon's map |
| Solid outline | The real brain |
| Orange dot | Tumour |
| Purple dot | Spot on the MRI |
| Blue dot | The same spot on the ultrasound |
| Green | Good, or kept |
| Red | Wrong, or dropped |

The millimetre numbers on slide 6 are real (RESECT Case 12).

## Rubric coverage

Weights come from the official statewide rubric (scored 1–5, plus a hardware bonus).

| Rubric item | Weight | Slides |
|---|---|---|
| 01 Problem definition & relevance | 15% | 2 Map goes out of date (pre-op MRI, 2 cm shift, missed tumour); the notes cover the cost of an operating-room MRI · 3 Some ultrasound matches are wrong |
| 02 Quantum rationale & potential | 20% | 5 One qubit per match, superposition, sampling; "today a normal computer is just as good" · 10 What chips need to win (8× fewer errors, 80–200 qubits, under a second) |
| 03 Technical implementation (Qiskit) | 20% | 9 Parameterized QAOA circuit, hybrid loop, Sampler primitive and transpiler, error suppression · 7 the app |
| 04 Results & validation | 10% | 6 One patient, three maps · 8 264 tests on 22 patients vs baselines, 95% ranges · 9 Real chip vs simulator |
| 05 Innovation & creativity | 10% | 4 and 6 The self-check alarm · real patients graded in mm (notes on 10) |
| 06 Presentation & communication | 15% | Short slides; one-sentence close (11); within time |
| 07 Q&A, teamwork & learning journey | 10% | 10 Next month · 11 Built solo by Neel Gurram · lessons in the notes on 11 |
| Hardware bonus, top tier (+5) | +5 | 9 Real IBM hardware, plus labels for simulator comparison, noise analysis and error suppression (only one is needed). Job IDs are in the footer. |
| Required limitations | — | 10 (notes) and LIMITATIONS.md |

## Before presenting
- Read the SAY script in each note aloud once with a timer; it should take about 4 minutes.
- Slide 7 plays `demo/anchor_demo_slide.mp4` (20 s) by itself, looping. Submit `demo/anchor_demo_short.mp4` (45 s) as the demo video.
- D-Wave needs paid or approved access, so it is not in the deck.
