import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import BrainView, { DISPLAY_CAP_MM, type LineState, type ViewState } from "./BrainView";
import { api, type Brain, type CaseInfo, type ProblemData, type SolveData, type SolverInfo } from "./api";
import { COLORS, ERROR_STOPS } from "./theme";
import Lab from "./Lab";

type Tab = "surgery" | "lab" | "results";

const STEPS = ["Load patient", "Open the skull", "Take ultrasound", "Pick trusted matches", "Correct the map"];

const fmt = (v: number | null | undefined, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "–" : v.toFixed(d));

export default function App() {
  const [brain, setBrain] = useState<Brain | null>(null);
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [solvers, setSolvers] = useState<SolverInfo[]>([]);
  const [cfg, setCfg] = useState({ case_id: "Case12", n_used: 8, k: 2, outlier_rate: 0.3, seed: 9 });
  const [problem, setProblem] = useState<ProblemData | null>(null);
  const [step, setStep] = useState(0);              // number of steps completed
  const [target, setTarget] = useState<Float32Array | null>(null);
  const [solves, setSolves] = useState<Record<string, SolveData>>({});
  const [active, setActive] = useState<string | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [lineStates, setLineStates] = useState<LineState[]>([]);
  const [flashNote, setFlashNote] = useState<string | null>(null);
  const [colorMode, setColorMode] = useState<"tissue" | "error">("tissue");
  const [scale, setScale] = useState(2);
  const [tab, setTab] = useState<Tab>("surgery");
  const [err, setErr] = useState<string | null>(null);
  const flashTimer = useRef<number | null>(null);

  useEffect(() => {
    api.brain().then(setBrain).catch(e => setErr(`Backend not reachable: ${e.message}`));
    api.cases().then(setCases).catch(() => {});
    api.solvers().then(setSolvers).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setBusy("load"); setErr(null);
    try {
      const p = await api.problem(cfg);
      setProblem(p); setStep(1); setTarget(null); setSolves({}); setActive(null); setApplied(null);
      setLineStates(p.candidates.map(() => "pending")); setColorMode("tissue");
    } catch (e: any) { setErr(e.message); } finally { setBusy(null); }
  }, [cfg]);

  const openSkull = () => { if (!problem) return; setTarget(problem.trueShift); setStep(2); };
  const ultrasound = () => setStep(3);

  const runSolver = async (id: string) => {
    if (!problem) return;
    setBusy(id); setErr(null); setActive(id);
    try {
      const r = solves[id] ?? await api.solve(problem.problem_id, id);
      setSolves(s => ({ ...s, [id]: r }));
      const final: LineState[] = r.result.selection.map(b => (b ? "kept" : "rejected"));
      const seq = [...r.result.samples].reverse();              // worst -> best of the top samples
      if (flashTimer.current) window.clearInterval(flashTimer.current);
      if (seq.length > 1) {
        let i = 0;
        setFlashNote(`Replaying ${seq.length} sampled answers from ${r.meta.label ?? id}`);
        flashTimer.current = window.setInterval(() => {
          if (i < seq.length) {
            setLineStates(seq[i].bits.map(b => (b ? "kept" : "rejected")));
            i++;
          } else {
            window.clearInterval(flashTimer.current!); flashTimer.current = null;
            setLineStates(final); setFlashNote(null);
          }
        }, 150);
      } else {
        setLineStates(final);
      }
      setStep(s => Math.max(s, 4));
    } catch (e: any) { setErr(`${id}: ${e.message}`); } finally { setBusy(null); }
  };

  const correct = () => {
    if (!active || !solves[active]) return;
    setTarget(solves[active].displacement); setApplied(active); setStep(5); setColorMode("error");
  };

  const cur = applied ? solves[applied] : null;
  const act = active ? solves[active] : null;

  const view: ViewState = useMemo(() => ({
    brain, problem, target, scale, colorMode,
    error: cur ? cur.error : null,
    showMri: step >= 1, showCandidates: step >= 3,
    lineStates, showHeld: step >= 5, animMs: 1800,
  }), [brain, problem, target, scale, colorMode, cur, step, lineStates]);

  const mapError = !problem ? null : step < 2 ? 0 : cur ? cur.evaluation.tre : problem.metrics.tre_uncorrected;
  // green only for a real correction: within 2x of the best possible (or under 3 mm)
  const fixed = !!cur && cur.evaluation.tre <= Math.max(3, 2 * cur.evaluation.tre_oracle);

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="mark" /> Anchor <span className="sub">quantum-checked brain-shift correction</span></div>
        <nav>
          {(["surgery", "lab", "results"] as Tab[]).map(t => (
            <button key={t} className={tab === t ? "tab on" : "tab"} onClick={() => setTab(t)}>
              {t === "surgery" ? "Surgery" : t === "lab" ? "Solver lab" : "Results"}
            </button>
          ))}
        </nav>
      </header>

      <main className={`body ${tab === "results" ? "results-wide" : tab === "lab" ? "lab-wide" : ""}`}>
        <section className="viewport">
          <BrainView s={view} />
          <div className="overlay tl">
            <div>Template brain for display. Errors are measured in patient space.</div>
            <div>Movement shown ×{scale}, capped at {DISPLAY_CAP_MM} mm on screen</div>
          </div>
          <div className="overlay bl legend">
            <span><i style={{ background: COLORS.mri }} /> MRI landmark (pre-op map)</span>
            {step >= 3 && <span><i style={{ background: COLORS.us }} /> Ultrasound candidate</span>}
            {step >= 4 && <span><i style={{ background: COLORS.kept }} /> Trusted</span>}
            {step >= 4 && <span><i style={{ background: COLORS.rejected }} /> Rejected</span>}
            {step >= 5 && <span><i style={{ background: COLORS.held }} /> Hidden check point</span>}
          </div>
          {colorMode === "error" && cur && (
            <div className="overlay br heat">
              <div className="heat-bar" style={{ background: `linear-gradient(90deg, ${ERROR_STOPS.map(s => `${s.hex} ${(s.mm / 5) * 100}%`).join(", ")})` }} />
              <div className="heat-ticks"><span>0</span><span>1</span><span>3</span><span>5+ mm</span></div>
              <div className="heat-label">Map error vs expert-landmark shift</div>
            </div>
          )}
          {flashNote && <div className="overlay tc flash">{flashNote}</div>}
          {err && <div className="overlay tc error">{err}</div>}
        </section>

        <aside className="rail">
          {tab === "surgery" && (
            <>
              <Step n={1} title={STEPS[0]} done={step >= 1} current={step === 0 || step === 1}>
                <p>Real landmark pairs from the RESECT study: points marked by experts on the pre-op MRI and again on ultrasound after the skull was opened.</p>
                <div className="row">
                  <label>Patient
                    <select value={cfg.case_id} onChange={e => setCfg({ ...cfg, case_id: e.target.value })}>
                      {cases.map(c => <option key={c.id} value={c.id}>{c.id} · shift {c.mean_shift_mm} mm</option>)}
                    </select>
                  </label>
                  <label>Bad matches
                    <select value={cfg.outlier_rate} onChange={e => setCfg({ ...cfg, outlier_rate: +e.target.value })}>
                      {[0, 0.2, 0.3, 0.4].map(v => <option key={v} value={v}>{Math.round(v * 100)}%</option>)}
                    </select>
                  </label>
                  <label>Landmarks
                    <select value={cfg.n_used} onChange={e => setCfg({ ...cfg, n_used: +e.target.value })}>
                      {[4, 6, 8, 10].map(v => <option key={v} value={v}>{v} ({v * cfg.k} qubits)</option>)}
                    </select>
                  </label>
                  <label>Seed
                    <input type="number" value={cfg.seed} min={0} onChange={e => setCfg({ ...cfg, seed: +e.target.value })} />
                  </label>
                </div>
                <button className="primary" disabled={!brain || busy === "load"} onClick={load}>
                  {busy === "load" ? "Loading…" : problem ? "Reload patient" : "Load patient"}
                </button>
              </Step>

              <Step n={2} title={STEPS[1]} done={step >= 2} current={step === 1} locked={step < 1}>
                <p>The brain sinks under the opening. The navigation map was made before surgery, so it stays where it was.</p>
                <button className="primary" disabled={step < 1} onClick={openSkull}>Open the skull</button>
                {step >= 2 && problem && (
                  <div className="stat big warn">Map is now off by <b>{fmt(problem.metrics.tre_uncorrected)} mm</b>
                    <small>average over {problem.metrics.n_held} hidden expert check points</small></div>
                )}
              </Step>

              <Step n={3} title={STEPS[2]} done={step >= 3} current={step === 2} locked={step < 2}>
                <p>Ultrasound suggests matches for each MRI landmark. Some are wrong: speckle, or a structure that looks similar.</p>
                <button className="primary" disabled={step < 2} onClick={ultrasound}>Take ultrasound</button>
                {step >= 3 && problem && (
                  <div className="stat">{problem.candidates.length} candidate matches for {problem.params.n_used} landmarks</div>
                )}
              </Step>

              <Step n={4} title={STEPS[3]} done={step >= 4} current={step === 3 || step === 4} locked={step < 3}>
                <p>Each candidate match is one qubit: 1 = trust it, 0 = reject it. The best answer is the largest set of matches that all agree with each other.</p>
                <div className="solvers">
                  {solvers.map(sv => (
                    <button key={sv.id} disabled={step < 3 || !sv.available || !!busy}
                            className={`solver ${sv.family} ${active === sv.id ? "on" : ""}`}
                            title={sv.available ? sv.desc : "No recorded run for this exact problem yet"}
                            onClick={() => runSolver(sv.id)}>
                      <span>{sv.label}</span>
                      <small>{busy === sv.id ? "running…" : sv.live ? "live" : sv.available ? "recorded" : "not run yet"}</small>
                    </button>
                  ))}
                </div>
                {act && <SolveSummary r={act} />}
              </Step>

              <Step n={5} title={STEPS[4]} done={step >= 5} current={step === 4 || step === 5} locked={step < 4}>
                <p>Warp the map onto the trusted matches, then check it against expert points the solver never saw.</p>
                <button className="primary" disabled={step < 4 || !act} onClick={correct}>
                  Correct the map{act ? ` with ${act.meta.label}` : ""}
                </button>
                {cur && problem && (
                  <div className={`stat big ${fixed ? "good" : "warn"}`}>
                    {fmt(problem.metrics.tre_uncorrected)} mm <span className="arrow">→</span> <b>{fmt(cur.evaluation.tre)} mm</b>
                    <small>{cur.meta.label}{fixed ? "" : " · still off: some trusted matches are wrong"} · best possible: {fmt(cur.evaluation.tre_oracle)} mm</small>
                  </div>
                )}
                {step >= 5 && (
                  <div className="toggles">
                    <button className={colorMode === "error" ? "chip on" : "chip"} onClick={() => setColorMode(colorMode === "error" ? "tissue" : "error")}>Error heatmap</button>
                    {[1, 2, 3].map(v => <button key={v} className={scale === v ? "chip on" : "chip"} onClick={() => setScale(v)}>×{v}</button>)}
                  </div>
                )}
              </Step>

              {Object.keys(solves).length > 0 && problem && (
                <div className="compare">
                  <div className="compare-title">Compared on this patient</div>
                  <table>
                    <thead><tr><th>Solver</th><th>Map error</th><th>Correct kept</th><th>vs optimum</th><th>Time</th></tr></thead>
                    <tbody>
                      {Object.values(solves).map(r => (
                        <tr key={r.solver} className={r.solver === applied ? "on" : ""}>
                          <td>{r.meta.label}{r.result.replay ? " *" : ""}</td>
                          <td>{fmt(r.evaluation.tre)} mm</td>
                          <td>{Math.round(r.evaluation.precision * 100)}%</td>
                          <td>{r.result.approx_ratio === null ? "n/a" : `${Math.round(r.result.approx_ratio * 100)}%`}</td>
                          <td>{r.result.wall_time < 1 ? `${Math.round(r.result.wall_time * 1000)} ms` : `${r.result.wall_time.toFixed(1)} s`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="foot">Unchanged map: {fmt(problem.metrics.tre_uncorrected)} mm. * recorded hardware run.</div>
                </div>
              )}
            </>
          )}
          {tab === "lab" && <Lab problem={problem} solve={act} />}
          {tab === "results" && <Lab problem={problem} solve={act} results />}
        </aside>
      </main>

      <footer className="strip">
        <Metric label="Patient's real brain shift" value={problem ? `${fmt(problem.case.mean_shift_mm)} mm` : "–"} sub={problem ? `max ${fmt(problem.case.max_shift_mm)} mm` : ""} />
        <Metric label="Navigation map error" value={mapError === null ? "–" : `${fmt(mapError)} mm`} sub={cur ? `after ${cur.meta.label}` : step >= 2 ? "uncorrected" : ""} tone={cur ? (fixed ? "good" : "warn") : step >= 2 ? "warn" : undefined} />
        <Metric label="Best possible" value={problem ? `${fmt(problem.metrics.tre_oracle)} mm` : "–"} sub="true matches only" />
        <Metric label="Qubits" value={problem ? `${problem.qubo.qubits}` : "–"} sub={problem ? `${problem.qubo.quadratic} couplings` : ""} />
        <Metric label="Solver" value={act ? act.meta.label ?? act.solver : "–"} sub={act ? (act.result.replay ? "recorded QPU run" : "computed live") : ""} />
      </footer>
    </div>
  );
}

function Step({ n, title, done, current, locked, children }: { n: number; title: string; done: boolean; current: boolean; locked?: boolean; children: React.ReactNode }) {
  return (
    <div className={`step ${done ? "done" : ""} ${current ? "current" : ""} ${locked ? "locked" : ""}`}>
      <div className="step-head"><span className="num">{n}</span>{title}</div>
      <div className="step-body">{children}</div>
    </div>
  );
}

function Metric({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "warn" }) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <div className="m-label">{label}</div>
      <div className="m-value">{value}</div>
      <div className="m-sub">{sub}</div>
    </div>
  );
}

function SolveSummary({ r }: { r: SolveData }) {
  const res = r.result, ev = r.evaluation;
  const c = res.circuit as any;
  return (
    <div className="summary">
      <div className="kv"><span>Trusted</span><b>{ev.n_selected} matches</b></div>
      <div className="kv"><span>Actually correct</span><b>{Math.round(ev.precision * 100)}%</b></div>
      {res.approx_ratio !== null && <div className="kv"><span>vs best answer</span><b>{Math.round(res.approx_ratio * 100)}%</b></div>}
      {res.p_optimal !== null && <div className="kv"><span>Shots at the exact optimum</span><b>{(res.p_optimal * 100).toFixed(1)}%</b></div>}
      {res.p_feasible !== null && <div className="kv"><span>Shots that are consistent</span><b>{(res.p_feasible * 100).toFixed(0)}%</b></div>}
      {c?.two_qubit_gates !== undefined && <div className="kv"><span>On IBM Heron</span><b>{c.two_qubit_gates} two-qubit gates</b></div>}
      {res.repaired && <div className="note">Best sample had a conflict; one clean-up pass removed it.</div>}
      {res.replay && <div className="note">Recorded on {String(res.provenance.backend ?? "QPU")} · job {String(res.provenance.job_id ?? "")}</div>}
    </div>
  );
}
