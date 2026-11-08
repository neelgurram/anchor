# Benchmark charter (written before any quantum run)

Fixed on 2026-11-05, before any QAOA, digitized-anneal, IBM or D-Wave result was looked at. Changes after this date are listed at the bottom, each with its reason.

| Field | Entry |
|---|---|
| **Problem, in one sentence** | During brain surgery, decide which ultrasound-to-MRI landmark matches the navigation system should trust when it corrects the map for brain shift. |
| **Problem type** | Optimization: maximum-weight clique on a consistency graph, written as a QUBO. |
| **Who has it** | Neurosurgeons and surgical-navigation vendors. Patients carry the risk: a stale or wrongly corrected map can lead to cutting the wrong tissue. |
| **Current method** | Feature matching followed by robust fitting (RANSAC-style outlier rejection), or simply trusting the matcher's top match. |
| **Classical baseline and metric** | Baselines: naive top-match, RANSAC rigid fit, exact maximum clique (networkx), simulated annealing. Headline metric: **target registration error (TRE) on held-out expert landmarks, in mm**. Solver metrics: approximation ratio, P(optimal), P(feasible), wall time, QPU time, transpiled 2-qubit depth. |
| **Instance sizes** | 22 RESECT patients. n_used ∈ {4, 6, 8, 10, 12} matched landmarks × k = 2 candidates each gives 8–24 binary variables (qubits). Outlier rate ∈ {0, 0.2, 0.4}. 5 seeds. |
| **Fixed parameters** | Consistency tolerance \|d_MRI − d_US\| ≤ 2.5 mm + 0.03·d_MRI. Chosen from the RESECT landmark geometry alone: the classical exact solution reaches 0.99 inlier precision and 0.94 recall. It is a property of the problem, not of any solver. Weights w = 1 + 0.05·score. Penalty P = 2·max(w). |
| **Success criteria for the prototype** | (1) The pipeline lowers held-out TRE vs no correction on real patients. (2) The consistency step beats naive matching when outliers are present. (3) Every quantum solver returns valid selections whose TRE is reported next to the classical optimum. (4) Simulator vs noise-model vs hardware comparison for the IBM runs. |
| **What we build** | The full pipeline (data → matches → graph → QUBO → solvers → warp → error), a live web demo with a 3D brain, a benchmark harness, and a small set of hardware runs. |
| **What we do not build** | A real ultrasound feature detector (matches are simulated around real expert landmarks). Patient-specific brain meshes (display uses a template brain). Anything clinical. |
| **What we will not claim** | Any quantum speedup or advantage. Exact classical maximum clique solves these sizes in milliseconds. |
| **Evidence that would stop the work** | If the consistency step did not beat naive matching on real data, the problem would not be worth solving with any solver, classical or quantum. Checked: it does (5.5 mm → 2.0 mm mean TRE at 30% outliers, n_used = 8). |

## Changes after the charter date

Each change applies identically to every solver. None changes which solver wins.

| Date | Change | Reason |
|---|---|---|
| 2026-11-05 | Thin-plate-spline warp now uses smoothing = 100 (was 0, exact interpolation). | With exact interpolation, one wrong match bent the surface by up to 148 mm. Measured at n_used = 8 with 30% outliers across 22 patients × 3 seeds (`summary.json → smoothing_check`), smoothing 0 → 100 moved TRE: naive 5.45 → 5.10 mm, exact max clique 2.02 → 1.87 mm, oracle 1.69 → 1.57 mm. Every method improves and the ranking is unchanged. Chosen on the classical solvers before the quantum benchmark. |
| 2026-11-05 | QAOA settings set to p = 3, CVaR α = 0.5, starting from a linear-ramp schedule (Δ = 1.0). First tried: p = 2, α = 0.25. | The first settings were tuning choices, not fixed in the charter. They were weak on 16-qubit instances, and the final ones are standard published defaults (CVaR-QAOA, linear-ramp start). The benchmark reports the final settings for every instance. |
| 2026-11-05 | Added a confidence map and alarm (`confidence.py`), after the benchmark. | New output, not a change to any solver or metric. The rule (hide each trusted match, predict it from the others; alarm if the mean miss exceeds a threshold or fewer than 5 matches are trusted) was written before the validation sweep. The threshold was then chosen on even-numbered patients only (it came out at 3 mm, the same as the "bad map" line) and tested on odd-numbered patients. A worst-miss variant was compared on the calibration patients only and gave the same test accuracy, so the pre-written mean rule was kept. |
| 2026-11-05 | The 3D view caps on-screen movement at 30 mm after the ×2 exaggeration. | Display only. Metrics are computed on the uncapped warp in patient space. The UI states the cap. |

## Result against the charter (2026-11-05 benchmark)
- **Criteria 1 and 2 are met.** On 264 paired instances, held-out TRE goes from 5.36 mm uncorrected and 5.57 mm naive to 2.19 mm exact max clique.
- **Criterion 3 is met on the simulator.** QAOA and digitized anneal reach the same TRE as exact (paired difference −0.02 ± 0.06 mm).
- **Criterion 4 is met (2026-11-08).** The 24 noise-study circuits ran on IBM ibm_fez, raw and with DD + twirling (48 runs). Hardware reached 83% of the noise model's consistent-shot rate and 6× random. In 42 of 48 runs the best shot was the exact optimum, with the same map error as exact. Error suppression did not help (85% of raw); the jobs ran hours apart, so drift is a confound. Details: `results/hardware/analysis.json`, `results/figures/hardware.png`.
- **A finding we did not expect, and report as-is:** RANSAC (rigid-fit inlier test) beats exact max clique by 0.17 ± 0.12 mm (paired). The reason is that pairwise-distance consistency is looser than a global rigid check, so the largest consistent set sometimes admits a decoy that happens to fit. The QUBO solves its problem optimally; the problem definition is what leaves this gap. The obvious next step is adding triplet or rigid-fit terms, which turns the QUBO into a higher-order (HUBO) problem.

