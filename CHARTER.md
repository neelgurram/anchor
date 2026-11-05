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
(none yet)
