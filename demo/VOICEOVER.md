# Demo voiceover (≈ 2 min, timed to `scripts/record_demo.py`)

The numbers are what the app shows live for RESECT Case12 (seed 9, 8 landmarks, 30% bad matches). If you change the case, re-read them off the screen.

| Beat (≈ s) | On screen | Line |
|---|---|---|
| 1 (0–4) | Title | "Brain surgeons steer with a map made from an MRI taken before surgery." |
| 2 (4–10) | Load patient: violet MRI landmarks | "This is a real patient. Experts marked these landmarks on the MRI and again on ultrasound during the operation." |
| 3 (10–18) | Open the skull: brain sags; map off by 19.6 mm | "Once the skull is opened, the brain sags. For this patient, the map is now off by almost two centimetres." |
| 4 (18–25) | Take ultrasound: blue candidates, grey lines | "Ultrasound can show where the brain went, but it's noisy. Each landmark gets several possible matches, and some of them are wrong." |
| 5 (25–37) | Naive → Correct the map: red bulge, 17.8 mm | "If we trust every top match, a few bad ones bend the whole map. It's still wrong by 18 millimetres." |
| 6 (37–55) | QAOA: answers flash, settle green and red | "So we ask which matches agree with each other. That's a maximum-clique problem, which we write as a QUBO and run on a quantum circuit. Each flash is one answer sampled from the circuit." |
| 7 (55–63) | Correct the map: blue/cyan, 1.4 mm | "Using only the trusted matches, the map snaps back to 1.4 millimetres, checked against expert points the solver never saw." |
| 8 (63–79) | Digitized anneal | "Here the same problem runs as an annealing schedule on gate hardware. We also ran it on a real D-Wave annealer and on IBM's Heron processor." |
| 9 (79–90) | Solver lab: circuit, Heron gate count | "This is one layer of the circuit. The three-layer version we ran needs over a thousand two-qubit gates on IBM Heron, at only sixteen qubits." |
| 10 (90–120) | Results: benchmark, figures, revisit trigger | "Across all 22 patients, checking consistency cuts map error from 5.6 to about 2 millimetres, and the quantum solvers match the exact classical answer. Classical computers still win at this size. We measured how much hardware error rates have to fall before that changes, and Anchor is built to swap the solver in when they do." |

**Before recording:** beat 8's second sentence is only true once `scripts/run_hardware.py` has run on IBM and D-Wave. Until then, say: "The same problem is ready to run on a real D-Wave annealer and on IBM's Heron processor."
