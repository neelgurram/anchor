# Demo voiceover (2:23, timed to `scripts/record_demo.py`)

The numbers are what the app shows live for RESECT Case12 (seed 9, 6 landmarks = 12 qubits, 30% bad matches). If you change the case, re-read them off the screen. Times are measured from the recorded `demo/anchor_demo.mp4`.

| Beat (s) | On screen | Line |
|---|---|---|
| 1 (0–8) | Title, brain | "Brain surgeons steer with a map made from an MRI taken before surgery." |
| 2 (8–13) | Load patient: violet MRI landmarks | "A real patient. Experts marked these points on the MRI and on ultrasound." |
| 3 (13–22) | Open the skull: brain sags; map off by 19.6 mm | "Once the skull is opened, the brain sags. For this patient, the map is now off by almost two centimetres." |
| 4 (22–30) | Take ultrasound: blue candidates, grey lines | "Ultrasound shows where the brain went, but it's noisy, and some matches are wrong." |
| 5 (30–45) | Naive → Correct the map: red map, 16.5 mm, "Do not trust this update" | "Trust every top match, and the bad ones bend the map: still sixteen millimetres off. But Anchor checks its own work. It hides each match and checks it against the others. They disagree, so it raises an alarm." |
| 6 (45–60) | QAOA: answers flash, settle green and red | "So we ask which matches agree with each other. That's a maximum-clique problem. We write it as a QUBO and run it on a quantum circuit. Each flash is one answer sampled from the circuit." |
| 7 (60–67) | Correct the map: 1.6 mm, Trusted | "With only the trusted matches, the map is back to 1.6 millimetres. Blue means trust it." |
| 8 (67–74) | Real error view | "And this is the real error, on expert points the solver never saw. It's small where Anchor said blue." |
| 9 (74–90) | IBM hardware: replay, job ID, Correct the map | "Now the same problem from a real IBM quantum computer, ibm_fez. These are the actual answers it returned. It picks the same matches, so we get the same 1.6 millimetre map, and the job ID is right here." |
| 10 (90–100) | Solver lab: circuit, gate counts | "This is one layer of the circuit. At just twelve qubits it already needs about 170 two-qubit gates on IBM hardware, and the deeper versions need over 500." |
| 11 (100–111) | Results: benchmark table and chart | "Across 22 patients, checking consistency cuts map error from 5.6 to about 2 millimetres. Quantum matches the exact classical answer. A classical method, RANSAC, is slightly better, and we say so." |
| 12 (111–123) | When would quantum hardware be worth revisiting? | "Classical computers still win at this size. This table shows how much hardware error rates have to fall before the quantum version is worth running on real cases." |
| 13 (123–131) | Does the confidence map tell the truth? | "On patients it was never tuned on, the alarm caught 93 percent of naive maps and left 84 percent of good maps alone." |
| 14 (131–143) | What happened on a real quantum computer? | "On the real IBM chip, 42 of 48 runs found the best answer, close to what our noise model predicted. When better quantum hardware arrives, Anchor swaps it in." |

**Things not to say:** "predict the shift" (Anchor measures it), "quantum advantage" or "quantum beat classical" (it tied), or that the colours are a quantum feature (they come from the hide-one check, which works with any solver). D-Wave has not run yet; only mention it once `scripts/run_hardware.py --dwave` has.
