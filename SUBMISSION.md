# DeepStation submission: Miami-Dade College IBM Quantum Qiskit Hackathon

**Deadline: Wednesday, Nov 11, 2026, 3:00 PM ET.** Late submissions are not judged. The top 5 teams present live at 6:30 PM: 5 minutes of talk, then 5 minutes of questions. The same 11-slide deck works for that.

## Checklist
- [ ] Registered on the hackathon page, and a team created (solo team is fine).
- [ ] **Project name:** Anchor
- [ ] **Description:** paste the text below.
- [ ] **Video, 5 minutes max, in your own voice** (no robotic AI voice): see "Recording the video" below. Save the submission first, then upload the MP4.
- [ ] **GitHub repository:** https://github.com/neelgurram/anchor. It is **private** right now, so judges can't open it. Make it public first, or ask in the hackathon chat how to share it.
- [ ] **Files:**
  - the video (MP4)
  - `notebooks/Anchor_walkthrough.ipynb` (already has outputs, including the IBM run)
  - the slides as PDF (Share › Export on the deck)
  - `results/figures/hardware.png`, `results/figures/noise.png`, `results/figures/tre_by_solver.png`
- [ ] Click **Submit Project**. You can still use **Update Submission** until the hackathon ends.

## Description (paste this)

**The problem.** Before brain surgery, the patient gets an MRI, and during the operation a navigation system uses it like a GPS for the surgeon's tools. Once the skull is opened, the brain sags and shifts by up to 2 cm ("brain shift"), so the map is wrong. Surgeons can then leave tumour behind or cut healthy brain. The only full fix, an MRI scanner in the operating room, costs millions, and few hospitals have one. A cheap live ultrasound can update the map by matching landmarks between the two scans. But ultrasound is blurry, so some matches are wrong, and one wrong match bends the whole map.

**Our solution and the quantum opportunity.** Anchor decides which matches to trust. Correct matches all move together, so they agree with each other. Anchor keeps the biggest group that agrees (a maximum-clique problem), fixes the map with it, and checks its own fix, sounding an alarm when the map can't be trusted. We wrote the choice as a QUBO: one qubit per match, 1 = keep, 0 = drop. A parameterized QAOA circuit in Qiskit puts every possible group in superposition, and we sample it thousands of times to keep the best group. A classical optimizer tunes the circuit in a hybrid loop. Max clique is hard in general, so this is the kind of choice quantum optimizers may speed up as chips improve.

**Results on a simulator.** We tested 22 real patients from RESECT, a public dataset, in 264 tests. Each fix was graded on expert landmarks Anchor never saw.
- Trusting every match left the map 5.6 mm off.
- Anchor brought it to 2.2 mm, on the quantum simulator and on a normal computer alike.
- The standard RANSAC method did slightly better (2.0 mm), and we report it.
- On one patient, Anchor took the map from 19.6 mm off to 1.6 mm.

**Results on real IBM quantum hardware.** We ran 48 puzzles (6–12 qubits) on IBM's ibm_fez (Heron r2) chip using Qiskit Runtime's Sampler primitive, at 2,000 shots each. The circuits were transpiled at optimization level 3 and sent twice: once raw, and once with error suppression (dynamical decoupling and twirling). The job IDs are dbnuils4148s7391lgkg and dbnvsu8qtr0c73adohg0.
- In 42 of 48 runs, the chip's best answer was the perfect one.
- The fixed map was as good as a normal computer's (2.3 mm vs 2.2 mm).
- We compared the hardware with a perfect simulator and a noisy-chip model. The chip got 83% of the valid answers the noise model predicted, and 6× more than random guessing.
- Error suppression gave no gain on this run.

**Honest conclusion.** Quantum ties a normal computer today. To win at surgical scale, chips need about 8× fewer errors, 80–200 qubits, and answers in under a second. The code, notebook, raw hardware results and app are in the repository.

## Recording the video (about 4.5 minutes)
The rules ask for background, a quantum summary, results, and how the hardware run worked. The 11 slides cover all of it, and the SAY script in each slide's notes is about 4.5 minutes of talk.

1. Export the deck to PowerPoint (Share › Export).
2. In PowerPoint, use **Record** › From Beginning. Read the SAY script on each slide and let the demo clip play on slide 7.
3. Use **File › Export › Create a Video** to save an MP4.

Any screen recorder with your microphone also works, for example Windows Snipping Tool's record mode or OBS. Check the length is under 5:00 before uploading.
