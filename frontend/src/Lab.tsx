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

function Results() {
  const [bench, setBench] = useState<any | null>(null);
  const [hw, setHw] = useState<any[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    api.benchmark().then(setBench).catch(e => setMsg(e.message));
    api.hardware().then(setHw).catch(() => setHw([]));
  }, []);
  return (
    <div className="panel lab">
      <h3>Benchmark across all 22 patients</h3>
      {!bench && <p className="muted">{msg ?? "Loading…"}</p>}
      {bench?.headline && (
        <table>
          <thead><tr><th>Solver</th><th>Map error</th><th>Correct kept</th><th>vs optimum</th></tr></thead>
          <tbody>{bench.headline.map((r: any) => (
            <tr key={r.solver}><td>{r.label}</td><td>{r.tre.toFixed(2)} ± {r.tre_ci.toFixed(2)} mm</td><td>{Math.round(r.precision * 100)}%</td><td>{r.approx_ratio === null ? "n/a" : `${Math.round(r.approx_ratio * 100)}%`}</td></tr>
          ))}</tbody>
        </table>
      )}
      {bench?.figures?.map((f: string) => <img key={f} className="fig" src={`/api/figure/${f}`} alt={f} />)}
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
