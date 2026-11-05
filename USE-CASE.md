# Use case: Anchor

## 1. The problem
Brain-tumour surgeons steer with a navigation system: a 3D map built from an MRI taken before the operation. As soon as the skull is opened, the brain sags under gravity and fluid loss. It shifts by about 5 mm on average and up to 2 cm in some patients, so the map no longer matches the patient on the table. A surgeon guided by a stale map can leave tumour behind or cut healthy tissue. The map can be corrected live: ultrasound sees where landmarks are now, and the MRI says where they were. But ultrasound is noisy, and some matches are wrong. **One wrong match bends the whole corrected map**, so the hard decision is *which matches to trust*.

## 2. Who has this problem
- **Neurosurgeons** removing gliomas and metastases, where how much tumour is removed is tied to survival.
- **Surgical-navigation makers**, whose systems must run the correction in the operating room.
- **Patients**, who carry the risk.

Tens of thousands of brain-tumour operations a year in the US alone face the problem. The hospitals with the least equipment feel it most: they lack an intra-operative MRI suite, which costs millions of dollars.

## 3. How it's solved today
- **Ignore it.** Surgeons mentally adjust for a map they know is drifting.
- **Intra-operative MRI.** Accurate, but it costs millions, interrupts surgery, and few hospitals have it.
- **Ultrasound-based correction.** Match features, reject outliers with RANSAC-style fitting, then warp the map.

Our baseline is that pipeline on real patient landmarks (RESECT, 22 patients). Uncorrected error is 5.4 mm. Trusting the top match gives 5.6 mm. RANSAC gives 2.0 mm. The exact max-clique answer to our QUBO gives 2.2 mm. The best possible with these landmarks is 1.8 mm. Exact classical solve time is about 1 ms.

## 4. What "better" is worth
- **Accuracy:** each millimetre of navigation error removed is a millimetre less margin the surgeon must leave. The correction step takes the error from 5.6 mm (naive) to about 2 mm, a 3.4 mm improvement on real patients.
- **Robustness:** at 40% bad matches the naive method's error is 5.8 mm, while the consistency-checked map holds at 1.9 mm.
- **Cost:** ultrasound correction uses equipment many hospitals already own, instead of an intra-operative MRI suite that costs millions.

## 5. The quantum shape
**Optimization.** The question "Which matches agree with each other?" is a maximum-weight clique problem, which is NP-hard in general.
- Each candidate match is one binary variable (one qubit).
- Every pair of matches that disagree gets a QUBO penalty.

This form runs natively on both quantum models:
- **gate-based:** QAOA, and digitized annealing as linear-ramp QAOA, on IBM Heron;
- **annealing:** a D-Wave Advantage quantum annealer.

That lets us compare gate-based and annealing hardware on the same problem.

## 6. The honest problem-size gap
| | Variables (qubits) |
|---|---|
| Real clinical case (20–50 landmarks × 4 candidates) | 80–200 |
| This weekend, live on a simulator | ≤ 16 (benchmark), ≤ 20 (app) |
| This weekend, IBM Heron hardware | 6–12 |
| This weekend, D-Wave Advantage | up to 24 |

Exact classical max clique solves 160 candidates in about 50 ms. At today's two-qubit error rate (about 3.3×10⁻³), a 30-qubit, one-layer circuit has an error-free run less than 0.3% of the time.

## 7. What would have to be true
- **Hardware:** two-qubit error must fall to around 4×10⁻⁴ for 30-qubit circuits to run error-free half the time, and to around 10⁻⁴ for 100+ qubits. The other route is error-corrected logical qubits.
- **Latency:** an update in under a second on a machine that can sit in or near a hospital. Cloud queues of seconds to minutes do not fit.
- **Algorithms:** a richer consistency model, such as rigid-fit or triplet terms, so the optimisation beats RANSAC rather than just matching it.
- **Industry and regulation:** navigation software needs FDA clearance, and patient data must stay inside hospital privacy rules (no third-party cloud without review).

## 8. What we'll actually build this weekend
A working app:
- real RESECT patient landmarks;
- a 3D brain that sags when you "open the skull";
- ultrasound matches, some of them wrong;
- a button per solver: naive, RANSAC, exact, simulated annealing, QAOA, digitized anneal, and recorded IBM and D-Wave runs;
- the map warping back into place, with the error in mm checked against hidden expert landmarks.

Behind it:
- a benchmark across all 22 patients;
- a noise study (ideal simulator, Heron noise model, hardware);
- one batched IBM hardware job and a D-Wave series, replayed from their raw bitstrings.

## 9. Why anyone should care
Brain surgery is steered with a map that goes out of date the moment the skull opens, and fixing it hinges on knowing which ultrasound clues to trust. Anchor turns that trust decision into an optimisation problem that runs today on gate-based and annealing quantum computers, on real patient data. Classical computers still win at this size, and we measured how much hardware has to improve before that changes.
