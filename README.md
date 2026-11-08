# Anchor: quantum-checked brain-shift correction

**Qiskit Fall Fest 2026 · Miami-Dade College**

Once the skull is opened the brain sags, and the MRI-based navigation map goes stale. Anchor corrects the map from live ultrasound. Its hardest decision is **which ultrasound-to-MRI matches to trust**. Anchor writes that decision as a maximum-clique QUBO and solves it four ways:
- classical exact and heuristic solvers;
- gate-based QAOA;
- digitized annealing on gate hardware;
- a quantum annealer.

Every answer is scored the same way: map error in mm at expert landmarks the solver never saw, on real patients.

## Results (22 RESECT patients, `results/benchmark/summary.json`)
| Method | Map error (TRE) | Correct matches kept |
|---|---|---|
| No correction | 5.36 mm | — |
| Naive (trust top match) | 5.57 ± 0.63 mm | 68% |
| RANSAC (rigid-fit outlier rejection) | 2.02 ± 0.08 mm | 99% |
| Exact max clique (classical) | 2.19 ± 0.15 mm | 98% |
| Simulated annealing | 2.19 ± 0.15 mm | 98% |
| Digitized anneal (gate, Aer) | 2.19 ± 0.15 mm | 98% |
| QAOA (gate, Aer) | 2.17 ± 0.14 mm | 98% |
| Best possible (true matches only) | 1.78 mm | 100% |

The table covers 264 paired instances: 8–16 qubits, 20–40% bad matches, 95% bootstrap CIs.

- **Quantum vs exact:** QAOA and digitized annealing match exact max clique (paired difference −0.02 ± 0.06 mm). Per shot they are far behind simulated annealing: at 16 qubits, QAOA hits the optimum on 0.07% of shots against 79% for simulated annealing.
- **RANSAC beats the clique formulation** by 0.17 ± 0.12 mm. Its global rigid check is stricter than pairwise distance agreement. We report this as found (CHARTER.md).
- **Noise decides the schedule** (`results/noise`, IBM Heron noise model, the same 6–12-qubit instances the hardware run uses):
  - On the ideal simulator, the deep annealing schedule is best.
  - Under noise it collapses to 13% consistent shots at 12 qubits.
  - The shallow p = 2 schedule and QAOA p = 1 hold 29–34%.
  - Every variant stays well above random guessing (2%).

  The hardware run therefore sends all three variants.
- **Real hardware, IBM ibm_fez (Heron r2), 2026-11-07** (`results/hardware`, 48 runs, jobs `dbnuils4148s7391lgkg` with DD + twirling and `dbnvsu8qtr0c73adohg0` raw, 2,000 shots each):
  - Same 24 circuits as the noise study, 6–12 qubits. Every number is re-scored from the saved raw bitstrings (`scripts/analyze_hardware.py`).
  - The hardware got **83% of the consistent shots the noise model predicted**, and 6× more than random guessing. The model is a fair, slightly optimistic guide.
  - Depth decides, as predicted: at 12 qubits the deep anneal keeps 4–13% consistent shots, QAOA p = 1 keeps 22–33%.
  - In **42 of 48 runs the best of 2,000 shots was the exact optimum**, and the map error matched the exact solver (2.28 vs 2.21 mm average; uncorrected 12.6 mm). In the other 6, 5 maps came out worse.
  - Error suppression (XY4 dynamical decoupling + twirling) did not help: 85% as many consistent shots as raw. The two jobs ran hours apart, so calibration drift is part of that gap.
- **Confidence map and alarm** (`results/confidence`, 3,344 corrected maps):
  - Anchor checks its own correction without seeing the truth. It hides each trusted match, predicts it from the others, and colours the brain by how far the map could move.
  - The alarm threshold was set on even-numbered patients. On the odd-numbered ones it caught **66% of bad maps** (real error > 3 mm) and left **84% of good maps** alone. It caught **93% of bad naive maps**.
  - Where the map is blue, the real error at hidden expert landmarks is 1.3 mm (median). Where it is red, it is 3.5 mm.
  - Limits: it misses maps that are bad because too few landmarks cover a region. Adding the solver's other near-best answers to the map did not make it more accurate (Spearman 0.47 vs 0.48 with the hide-one check alone), and we report that as found.
- **No quantum advantage is claimed.** Exact classical max clique takes about 1 ms here and about 50 ms at 160 candidates. See `revisit_trigger` in the summary for the hardware error rates at which this would change.

## What's here
| Path | What it is |
|---|---|
| `backend/anchor/` | The pipeline. L0 data (`data.py`) → L1 candidate matches → L2 consistency graph → L3 QUBO → L4 solvers (`solvers/`) → L5 thin-plate-spline warp and TRE → L6 template-brain mesh → L9 FastAPI (`api.py`) |
| `frontend/` | React + react-three-fiber app: the five-step surgery flow with the confidence heatmap and alarm, solver lab and results |
| `scripts/run_benchmark.py` | The full benchmark and figures (`results/benchmark`, `results/figures`) |
| `backend/anchor/confidence.py` | Confidence map and alarm: hide-one check, per-vertex spread, alarm rule |
| `scripts/run_confidence.py` | Checks the confidence map and alarm against the truth (`results/confidence`) |
| `scripts/run_noise.py` | Noise study: ideal simulator vs IBM Heron noise model vs random (`results/noise`) |
| `scripts/run_hardware.py` | IBM Heron and D-Wave runs (credentials typed in at run time and never stored); raw bitstrings go to `results/hardware` |
| `notebooks/Anchor_walkthrough.ipynb` | End-to-end walkthrough for judges, with outputs |
| `CHARTER.md` | Benchmark charter written before any quantum run, plus a dated change log |
| `USE-CASE.md`, `LIMITATIONS.md` | Use-case canvas and honest limits |
| `data/resect/` | RESECT landmark files (CC BY 4.0, see its README) |

## Run it
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cd backend && ../.venv/Scripts/python -m uvicorn anchor.api:app --port 8030
cd frontend && npm install && npx vite --port 5180      # open http://localhost:5180
```
Tests: `cd backend && ../.venv/Scripts/python -m pytest -q` (39 tests: QUBO-vs-max-clique penalty check, endianness, TRE math, API contract, replay, confidence engine).

## Data
RESECT: Xiao et al., *Medical Physics* 2017, DOI 10.11582/2017.00004, CC BY 4.0. Only the landmark tag files are used.

## Honest limits
The candidate matcher is simulated around real expert landmarks, the 3D brain is a template used for display only, and the instances are small. See LIMITATIONS.md.
