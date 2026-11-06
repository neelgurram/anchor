import { useEffect, useState } from "react";
import { api, type ProblemData, type SolveData } from "./api";

export default function Lab({ problem, solve, results }: { problem: ProblemData | null; solve: SolveData | null; results?: boolean }) {
  return results ? <Results /> : <SolverLab problem={problem} solve={solve} />;
}

function SolverLab({ problem, solve }: { problem: ProblemData | null; solve: SolveData | null }) {
  const [circ, setCirc] = useState<{ svg: string; stats: any } | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => { setCirc(null); }, [problem?.problem_id]);

  if (!problem) return <div className="panel"><p>Load a patient on the Surgery tab first.</p></div>;
  const q = problem.qubo;
  return (
    <div className="panel lab">
      <h3>The problem the quantum computer sees</h3>
      <div className="kv"><span>Qubits (one per candidate match)</span><b>{q.qubits}</b></div>
      <div className="kv"><span>Consistent pairs (graph edges)</span><b>{problem.graph.n_edges}</b></div>
      <div className="kv"><span>Penalty couplings in the QUBO</span><b>{q.quadratic}</b></div>
      <div className="kv"><span>Best answer (classical exact)</span><b>{q.opt_size} matches</b></div>
      <p className="muted">Score = −(matches kept) + penalty × (pairs kept that disagree). The lowest score is the largest set of matches that all agree.</p>

      <h3>Circuit (one QAOA layer)</h3>
      {!circ && <button className="primary" disabled={loading} onClick={async () => { setLoading(true); try { setCirc(await api.circuit(problem.problem_id)); } finally { setLoading(false); } }}>{loading ? "Drawing…" : "Show circuit"}</button>}
      {circ && (
        <>
          <div className="kv"><span>After compiling for IBM Heron</span><b>{circ.stats.two_qubit_gates} two-qubit gates, depth {circ.stats.depth}</b></div>
          <div className="circuit" dangerouslySetInnerHTML={{ __html: circ.svg }} />
        </>
      )}

      <h3>Sampled answers{solve ? ` · ${solve.meta.label}` : ""}</h3>
      {!solve || solve.result.samples.length === 0
        ? <p className="muted">Run QAOA, digitized anneal, simulated annealing or a recorded QPU run to see its sampled bitstrings.</p>
        : <Samples s={solve} />}
      {solve?.result.provenance && (
        <details><summary>Provenance</summary><pre>{JSON.stringify(solve.result.provenance, null, 1)}</pre></details>
      )}
    </div>
  );
}

function Samples({ s }: { s: SolveData }) {
  const smp = s.result.samples;
  const max = Math.max(...smp.map(x => x.count));
  const best = Math.min(...smp.map(x => x.energy));
  return (
    <div className="samples">
      {smp.map((x, i) => (
        <div key={i} className="sample">
          <code>{x.bits.join("")}</code>
          <div className="bar"><div style={{ width: `${(x.count / max) * 100}%` }} className={x.energy === best ? "best" : ""} /></div>
          <span>{x.count}</span><span className="muted">E={x.energy.toFixed(2)}</span>
        </div>
      ))}
      <p className="muted">Top answers by score. Bits are candidate matches in order; green bar = lowest score found.</p>
    </div>
  );
}

const CAPTION: Record<string, string> = {
  "tre_by_solver.png": "Map error on hidden expert landmarks, same 264 instances for every solver.",
  "tre_vs_outlier.png": "1,650 classical instances: trusting the top match fails as soon as some matches are wrong.",
  "quality_vs_qubits.png": "After keeping the best shot, quantum solvers reach the optimum; per shot they are far behind simulated annealing.",
  "device_cost.png": "Why hardware struggles: circuit size grows fast, and every two-qubit gate can fail.",
  "classical_time.png": "Exact classical max clique stays far under a second at realistic sizes.",
  "noise.png": "Same circuits, ideal simulator vs IBM Heron noise model vs random guessing.",
};

const pct = (v: number | null | undefined, d = 0) => (v == null ? "n/a" : `${(v * 100).toFixed(d)}%`);

function Results() {
  const [bench, setBench] = useState<any | null>(null);
  const [noise, setNoise] = useState<any | null>(null);
  const [hw, setHw] = useState<any[] | null>(null);
  const [conf, setConf] = useState<any | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    api.benchmark().then(setBench).catch(e => setMsg(e.message));
    api.noise().then(setNoise).catch(() => setNoise(null));
    api.confidence().then(setConf).catch(() => setConf(null));
    api.hardware().then(setHw).catch(() => setHw([]));
  }, []);
  const pd = bench?.paired_tre_difference;
  return (
    <div className="panel lab">
      <h3>Benchmark across all 22 patients</h3>
      {!bench && <p className="muted">{msg ?? "Loading…"}</p>}
      {bench?.headline && (
        <>
          <table>
            <thead><tr><th>Solver</th><th>Map error</th><th>Correct kept</th><th>vs optimum</th><th>Shots optimal</th><th>Time</th></tr></thead>
            <tbody>{bench.headline.map((r: any) => (
              <tr key={r.solver}><td>{r.label}</td><td>{r.tre.toFixed(2)} ± {r.tre_ci.toFixed(2)} mm</td>
                <td>{pct(r.precision)}</td><td>{pct(r.approx_ratio)}</td><td>{pct(r.p_optimal, 1)}</td>
                <td>{r.wall_time_s < 1 ? `${Math.round(r.wall_time_s * 1000)} ms` : `${r.wall_time_s.toFixed(1)} s`}</td></tr>
            ))}</tbody>
          </table>
          <p className="muted">{bench.headline[0].n} instances (8–16 qubits, 20–40% bad matches), simulated live on Aer. ± is a 95% bootstrap interval.</p>
        </>
      )}
      {pd && (
        <div className="findings">
          <div className="kv"><span>Consistency check vs naive</span><b>{Math.abs(pd["exact-naive"].mean_mm).toFixed(2)} mm better</b></div>
          <div className="kv"><span>QAOA vs exact (paired)</span><b>{pd["qaoa-exact"].mean_mm.toFixed(2)} ± {pd["qaoa-exact"].ci95_mm.toFixed(2)} mm</b></div>
          <div className="kv"><span>Digitized anneal vs exact</span><b>{pd["danneal-exact"].mean_mm.toFixed(2)} ± {pd["danneal-exact"].ci95_mm.toFixed(2)} mm</b></div>
          <div className="kv"><span>Exact max clique vs RANSAC</span><b>+{pd["exact-ransac"].mean_mm.toFixed(2)} ± {pd["exact-ransac"].ci95_mm.toFixed(2)} mm</b></div>
          <p className="muted">RANSAC's global rigid check is stricter than pairwise distance agreement, so it beats the clique formulation slightly. We report it as found.</p>
        </div>
      )}
      {bench?.figures?.map((f: string) => (
        <figure key={f}><img className="fig" src={`/api/figure/${f}`} alt={CAPTION[f] ?? f} /><figcaption className="muted">{CAPTION[f]}</figcaption></figure>
      ))}
      {bench?.revisit_trigger && (
        <>
          <h3>When would quantum hardware be worth revisiting?</h3>
          <table>
            <thead><tr><th>Qubits</th><th>2q gates (p = 1)</th><th>Error-free runs today</th><th>2q error needed for 50%</th></tr></thead>
            <tbody>{bench.revisit_trigger.filter((r: any) => r.p === 1).map((r: any) => (
              <tr key={r.qubits}><td>{r.qubits}</td><td>{r.two_qubit_gates}</td><td>{pct(r.error_free_now, 1)}</td><td>{r.eps_needed_for_50pct.toExponential(1)}</td></tr>
            ))}</tbody>
          </table>
          <p className="muted">Heron median two-qubit error today: {bench.heron_median_2q_error.toExponential(1)}. A clinical case needs 50–200 qubits.</p>
        </>
      )}
      <h3>Does the confidence map tell the truth?</h3>
      {!conf && <p className="muted">Confidence study not run yet.</p>}
      {conf && (
        <>
          <div className="findings">
            <div className="kv"><span>Bad maps the alarm caught (patients it was not tuned on)</span><b>{pct(conf.alarm.test.sensitivity)}</b></div>
            <div className="kv"><span>Good maps it left alone</span><b>{pct(conf.alarm.test.specificity)}</b></div>
            <div className="kv"><span>Naive maps caught</span><b>{pct(conf.by_solver.naive.test.sensitivity)}</b></div>
            <div className="kv"><span>Real error where the map is blue vs red</span>
              <b>{conf.points_red_vs_blue.real_error_median_where_spread_lt_1mm.toFixed(1)} vs {conf.points_red_vs_blue.real_error_median_where_spread_gt_5mm.toFixed(1)} mm</b></div>
            <p className="muted">
              The alarm threshold ({conf.alarm.threshold_mm} mm) was chosen on even-numbered patients and tested on odd-numbered ones.
              It catches wrong matches well. It misses maps that are bad because too few landmarks cover the region, a failure no
              check on the matches can see. Adding the solver's other near-best answers did not sharpen the map
              (ρ {conf.spread_vs_real_spearman.toFixed(2)} vs {conf.spread_vs_real_spearman_hide_one_only.toFixed(2)} with the hide-one check alone).
            </p>
          </div>
          <figure><img className="fig" src="/api/figure/confidence.png" alt="Confidence validation" />
            <figcaption className="muted">{conf.n_maps.toLocaleString()} corrected maps, 22 patients. Nothing in the confidence engine sees the truth.</figcaption></figure>
        </>
      )}
      <h3>Noise analysis</h3>
      {!noise && <p className="muted">Noise-model study not run yet.</p>}
      {noise && (
        <>
          <img className="fig" src="/api/figure/noise.png" alt={CAPTION["noise.png"]} />
          <figcaption className="muted">{CAPTION["noise.png"]}</figcaption>
        </>
      )}
      <h3>Recorded quantum hardware runs</h3>
      {hw && hw.length === 0 && <p className="muted">No hardware runs recorded yet.</p>}
      {hw && hw.length > 0 && (
        <table>
          <thead><tr><th>Device</th><th>Problem</th><th>Job</th></tr></thead>
          <tbody>{hw.map((r, i) => (
            <tr key={i}><td>{r.backend}</td><td>{r.params.case_id} · {r.params.n_used * r.params.k}q · {r.label}</td><td><code>{String(r.job_id).slice(0, 14)}</code></td></tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}
