# Limitations

What this project does not do, and what we do not claim.

## No quantum advantage
Exact classical maximum clique solves every instance here in milliseconds. At the sizes current hardware can run (≤ 24 variables), the quantum solvers are slower and no better than the classical exact answer. We claim a **correct mapping**, an **honest benchmark**, and a **measured gap**: `results/benchmark/summary.json → revisit_trigger` gives the two-qubit error rate a Heron-class device would need before a run at a given size is mostly error-free.

## The ultrasound matcher is simulated
The landmarks are real. Each RESECT patient has expert-placed MRI and pre-resection ultrasound pairs. The **candidate matches** are generated around them:
- the true partner, with 0.5 mm jitter, plus decoys;
- a decoy is either a "swap" (another landmark's position) or "speckle" (4–15 mm away);
- with probability `outlier_rate`, a decoy outscores the true match.

A real system needs an ultrasound feature detector and descriptor matcher. We did not build one.

## Template brain, display only
The 3D brain is the fsaverage6 template (FreeSurfer), not the patient's anatomy. Each patient's landmarks are translated onto it, never rotated or scaled, only for display. Movement on screen is exaggerated ×2 and capped at 30 mm, and the UI says so. **Every error number is computed in the patient's own scanner space** on held-out expert landmarks.

## Small instances
- **Gate-based:** live simulation is capped at 20 qubits. The IBM hardware set is 6–12 qubits.
- **D-Wave:** goes up to 24 variables.

A clinical case could have 50–200 candidate matches: 20–50 landmarks × 4 candidates. See USE-CASE.md §6.

## Hardware runs are few and recorded
- **Budgets:** the IBM Open Plan gives 10 QPU minutes per 28 days; the D-Wave Leap trial gives 60 seconds.
- **The runs:** one batched IBM job with mitigation and one without, plus a short series of D-Wave problems.
- **In the app:** the hardware runs are replayed from saved raw bitstrings and re-scored live. They are labelled "recorded" with job and problem IDs.

## Latency and the operating room
A cloud QPU call takes seconds to minutes in the queue. An intra-operative update has roughly a 1-second budget. Nothing here could run in surgery today, and the classical solver is what a product would ship.

## Data and regulation
RESECT is public and anonymized (CC BY 4.0), so sending it to a cloud QPU is fine. Real patient data could not go to a third-party cloud without a privacy and security review. Any clinical use would need regulatory clearance, for example FDA 510(k) for navigation software.

## Choices made after the charter date
Listed with reasons in CHARTER.md:
- TPS smoothing;
- the final QAOA settings;
- the on-screen movement cap.

Each applies identically to every solver.

## Warp model
A thin-plate spline fitted to 3–12 matched landmarks is a coarse model of brain deformation. It cannot capture:
- resection cavities;
- tissue that is removed;
- shift far from the landmarks.

Biomechanical models (FEM) do better and are out of scope.
