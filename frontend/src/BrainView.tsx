import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Brain, ProblemData, Vec3 } from "./api";
import { COLORS, errorColor } from "./theme";

export type LineState = "hidden" | "pending" | "kept" | "rejected";

export interface ViewState {
  brain: Brain | null;
  problem: ProblemData | null;
  target: Float32Array | null;     // displacement the surface should animate to (scene mm)
  scale: number;                   // display exaggeration factor (shown in the UI)
  colorMode: "tissue" | "error";
  error: Float32Array | null;
  showMri: boolean;
  showCandidates: boolean;
  lineStates: LineState[];         // per candidate
  showHeld: boolean;
  animMs: number;
}

export const DISPLAY_CAP_MM = 30;
const TISSUE = new THREE.Color("#c7a7a2");
const TISSUE_SITE = new THREE.Color("#d9b2a6");

function easeInOut(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function BrainMesh({ s }: { s: ViewState }) {
  const brain = s.brain!;
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(brain.positions.slice(), 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(brain.n_vertices * 3), 3));
    g.setIndex(new THREE.BufferAttribute(brain.indices, 1));
    g.computeVertexNormals();
    return g;
  }, [brain]);

  const anim = useRef({
    cur: new Float32Array(brain.n_vertices * 3),
    from: new Float32Array(brain.n_vertices * 3),
    to: new Float32Array(brain.n_vertices * 3),
    t: 1, dur: 1, dirty: true,
  });

  // new target -> start a morph from wherever the surface is now
  useEffect(() => {
    const a = anim.current;
    a.from.set(a.cur);
    if (s.target) a.to.set(s.target); else a.to.fill(0);
    a.t = 0;
    a.dur = Math.max(0.05, s.animMs / 1000);
  }, [s.target, s.animMs]);

  useEffect(() => { anim.current.dirty = true; }, [s.scale]);

  // vertex colours: tissue, a faint warm tint over the craniotomy region, or the error heatmap
  useEffect(() => {
    const col = geo.getAttribute("color") as THREE.BufferAttribute;
    const arr = col.array as Float32Array;
    const w = s.problem?.weight;
    const c = new THREE.Color();
    for (let i = 0; i < brain.n_vertices; i++) {
      const wi = w ? w[i] : 0;
      c.copy(TISSUE).lerp(TISSUE_SITE, wi * 0.6);
      if (s.colorMode === "error" && s.error && wi > 0.005) {
        const f = Math.min(1, wi / 0.12);                       // full colour across the corrected region, soft rim
        c.lerp(errorColor(s.error[i]), f * f * (3 - 2 * f));
      }
      arr[3 * i] = c.r; arr[3 * i + 1] = c.g; arr[3 * i + 2] = c.b;
    }
    col.needsUpdate = true;
  }, [geo, brain, s.problem, s.colorMode, s.error]);

  useFrame((_, dt) => {
    const a = anim.current;
    if (a.t >= 1 && !a.dirty) return;
    if (a.t < 1) {
      a.t = Math.min(1, a.t + dt / a.dur);
      const e = easeInOut(a.t);
      for (let i = 0; i < a.cur.length; i++) a.cur[i] = a.from[i] + (a.to[i] - a.from[i]) * e;
    }
    const pos = geo.getAttribute("position") as THREE.BufferAttribute;
    const p = pos.array as Float32Array;
    const base = brain.positions;
    // On-screen movement is capped after exaggeration so a wild warp reads as a dent, not streaks.
    const cap2 = DISPLAY_CAP_MM * DISPLAY_CAP_MM;
    for (let i = 0; i < p.length; i += 3) {
      let dx = a.cur[i] * s.scale, dy = a.cur[i + 1] * s.scale, dz = a.cur[i + 2] * s.scale;
      const m2 = dx * dx + dy * dy + dz * dz;
      if (m2 > cap2) { const k = DISPLAY_CAP_MM / Math.sqrt(m2); dx *= k; dy *= k; dz *= k; }
      p[i] = base[i] + dx; p[i + 1] = base[i + 1] + dy; p[i + 2] = base[i + 2] + dz;
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();
    a.dirty = false;
  });

  return (
    <mesh geometry={geo}>
      <meshStandardMaterial vertexColors roughness={0.62} metalness={0.04} />
    </mesh>
  );
}

function Dots({ pts, color, r = 1.7, opacity = 1 }: { pts: Vec3[]; color: string; r?: number; opacity?: number }) {
  return (
    <group>
      {pts.map((p, i) => (
        <mesh key={i} position={p} renderOrder={10}>
          <sphereGeometry args={[r, 14, 10]} />
          <meshBasicMaterial color={color} depthTest={false} transparent opacity={opacity} />
        </mesh>
      ))}
    </group>
  );
}

function Craniotomy({ site, normal }: { site: Vec3; normal: Vec3 }) {
  const q = useMemo(() => new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 0, 1), new THREE.Vector3(...normal).normalize()), [normal]);
  const p = useMemo(() => new THREE.Vector3(...site).addScaledVector(new THREE.Vector3(...normal), 2), [site, normal]);
  return (
    <mesh position={p} quaternion={q} renderOrder={5}>
      <torusGeometry args={[30, 0.45, 8, 96]} />
      <meshBasicMaterial color={COLORS.accent} transparent opacity={0.55} />
    </mesh>
  );
}

function CameraRig({ problem }: { problem: ProblemData | null }) {
  const { camera, controls } = useThree() as any;
  const goal = useRef<{ pos: THREE.Vector3; look: THREE.Vector3; t: number } | null>(null);
  useEffect(() => {
    if (!problem) return;
    const site = new THREE.Vector3(...problem.placement.site);
    const n = new THREE.Vector3(...problem.placement.normal).normalize();
    // Three-quarter lateral view: recognisable as a brain, craniotomy facing the camera.
    const lat = new THREE.Vector3(Math.sign(site.x) || 1, 0, 0);
    const dir = n.clone().multiplyScalar(0.65).add(lat.multiplyScalar(0.7)).add(new THREE.Vector3(0, 0.3, 0)).normalize();
    const look = site.clone().multiplyScalar(0.5);            // halfway between site and brain centre
    const pos = look.clone().addScaledVector(dir, 400);
    goal.current = { pos, look, t: 0 };
  }, [problem]);
  useFrame((_, dt) => {
    const g = goal.current;
    if (!g || g.t >= 1) return;
    g.t = Math.min(1, g.t + dt / 1.6);
    const e = easeInOut(g.t);
    camera.position.lerp(g.pos, e * 0.25 + 0.02);
    if (controls) { controls.target.lerp(g.look, e * 0.25 + 0.02); controls.update(); }
  });
  return null;
}

const LINE_COLOR: Record<LineState, string> = {
  hidden: "#000000", pending: "#8d99a8", kept: COLORS.kept, rejected: COLORS.rejected,
};

export default function BrainView({ s }: { s: ViewState }) {
  const p = s.problem;
  return (
    <Canvas camera={{ position: [260, 160, 300], fov: 32, near: 1, far: 3000 }} dpr={[1, 2]}
            gl={{ antialias: true }} style={{ background: COLORS.bg }}>
      <ambientLight intensity={0.55} />
      <directionalLight position={[120, 260, 180]} intensity={1.25} />
      <directionalLight position={[-200, -60, -150]} intensity={0.35} color="#7aa7ff" />
      {s.brain && <BrainMesh s={s} />}
      {p && <Craniotomy site={p.placement.site} normal={p.placement.normal} />}
      {p && s.showMri && <Dots pts={p.landmarks.mri_used} color={COLORS.mri} />}
      {p && s.showCandidates && (
        <>
          <Dots pts={p.candidates.map(c => c.pos)} color={COLORS.us} r={1.35} />
          {p.candidates.map((c, i) => {
            const st = s.lineStates[i] ?? "pending";
            if (st === "hidden") return null;
            return (
              <Line key={c.id} points={[p.landmarks.mri_used[c.landmark], c.pos]} color={LINE_COLOR[st]}
                    lineWidth={st === "kept" ? 3.2 : 1.6} transparent opacity={st === "rejected" ? 0.45 : 0.95}
                    depthTest={false} renderOrder={9} />
            );
          })}
        </>
      )}
      {p && s.showHeld && <Dots pts={p.landmarks.us_held} color={COLORS.held} r={1.2} opacity={0.9} />}
      <OrbitControls makeDefault enableDamping dampingFactor={0.08} minDistance={60} maxDistance={900} />
      <CameraRig problem={p} />
    </Canvas>
  );
}
