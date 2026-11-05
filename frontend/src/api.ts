// Thin client for the Anchor FastAPI backend. Every number on screen comes from here.

export type Vec3 = [number, number, number];

export interface CaseInfo { id: string; n_landmarks: number; mean_shift_mm: number; max_shift_mm: number }

export interface SolverInfo {
  id: string; label: string; family: string; desc: string; live: boolean; available: boolean;
}

export interface Brain {
  n_vertices: number; positions: Float32Array; indices: Uint32Array; region: Uint8Array;
  regions: { id: number; name: string; color: string }[];
  ventricles: { positions: Float32Array; indices: Uint32Array };
}

export interface Candidate { id: number; landmark: number; pos: Vec3; score: number; kind: string; true: boolean }

export interface ProblemData {
  problem_id: string;
  params: { case_id: string; n_used: number; k: number; outlier_rate: number; seed: number;
            tolerance: { tau_mm: number; tau_rel: number } };
  case: CaseInfo & { id: string };
  placement: { site: Vec3; normal: Vec3; offset: Vec3; note: string };
  landmarks: { mri_used: Vec3[]; us_used_true: Vec3[]; mri_held: Vec3[]; us_held: Vec3[] };
  candidates: Candidate[];
  graph: { n_nodes: number; n_edges: number; edges: [number, number][] };
  qubo: { qubits: number; linear: number; quadratic: number; opt_weight: number; opt_size: number };
  metrics: { tre_uncorrected: number; tre_oracle: number; n_held: number };
  trueShift: Float32Array; weight: Float32Array; trueShiftMax: number;
}

export interface Sample { bits: number[]; count: number; energy: number }

export interface SolveData {
  solver: string;
  result: {
    solver: string; selection: number[]; raw_best: number[]; repaired: boolean; best_energy: number;
    approx_ratio: number | null; p_optimal: number | null; p_feasible: number | null;
    expected_ratio: number | null; wall_time: number; qpu_time: number | null;
    samples: Sample[]; circuit: Record<string, unknown> | null; provenance: Record<string, unknown>;
    replay: boolean;
  };
  evaluation: {
    tre_uncorrected: number; tre: number; tre_max: number; tre_oracle: number;
    map_error_max: number; map_error_mean: number; n_selected: number;
    precision: number; recall: number; warp_kind: string;
  };
  meta: { label?: string; family?: string; desc?: string };
  displacement: Float32Array; error: Float32Array;
  surface_error_max_mm: number; surface_displacement_max_mm: number;
  display_clip_mm: number; display_clipped_fraction: number;
}

function b64(s: string): ArrayBuffer {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}
const f32 = (s: string) => new Float32Array(b64(s));
const u32 = (s: string) => new Uint32Array(b64(s));

async function call<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail ?? msg; } catch { /* keep status */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  cases: () => call<CaseInfo[]>("/api/cases"),
  solvers: () => call<SolverInfo[]>("/api/solvers"),
  async brain(): Promise<Brain> {
    const j = await call<any>("/api/brain");
    return {
      n_vertices: j.n_vertices, positions: f32(j.positions), indices: u32(j.indices),
      region: new Uint8Array(b64(j.region)), regions: j.regions,
      ventricles: { positions: f32(j.ventricles.positions), indices: u32(j.ventricles.indices) },
    };
  },
  async problem(req: { case_id: string; n_used: number; k: number; outlier_rate: number; seed: number }): Promise<ProblemData> {
    const j = await call<any>("/api/problem", req);
    return { ...j, trueShift: f32(j.true_shift.displacement), weight: f32(j.true_shift.weight),
             trueShiftMax: j.true_shift.max_mm };
  },
  async solve(problem_id: string, solver: string): Promise<SolveData> {
    const j = await call<any>("/api/solve", { problem_id, solver, params: {} });
    return { ...j, solver, displacement: f32(j.displacement), error: f32(j.error) };
  },
  circuit: (problem_id: string) => call<{ svg: string; stats: Record<string, unknown> }>(`/api/circuit/${problem_id}`),
  benchmark: () => call<any>("/api/benchmark"),
  hardware: () => call<any[]>("/api/hardware"),
};
