// Cinematic clips for the slide deck. Same real data as the app (Case12, seed 9), styled for video.
//   /film.html?scene=hero|shift|bad|fix            plays live, looping
//   /film.html?scene=...&capture=1                 frame-stepped by scripts/record_film.py via window.__render(t)
/* eslint-disable react-hooks/immutability */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import { Bloom, EffectComposer, SMAA, Vignette } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { api, type Brain, type ProblemData, type SolveData, type Vec3 } from "../api";
import { errorColor } from "../theme";

const DEMO = { case_id: "Case12", n_used: 6, k: 2, outlier_rate: 0.3, seed: 9 };
type SceneId = "hero" | "shift" | "bad" | "fix";
const qs = new URLSearchParams(location.search);
const SCENE = (qs.get("scene") ?? "hero") as SceneId;
const CAPTURE = qs.has("capture");
export const DUR: Record<SceneId, number> = { hero: 12, shift: 8, bad: 8, fix: 8 };
const SCALE = 2;            // on-screen exaggeration of real movement (stated in the clip)
const CAP = 30;             // mm on screen, same cap as the app

const clock = { t: 0 };
const BASE = new THREE.Color("#8d96a1");
const SITE = new THREE.Color("#a3adb9");
const CYAN = new THREE.Color("#5fd8ff");
const GREEN = new THREE.Color("#3ddc97");
const RED = new THREE.Color("#ff5d6c");
const VIOLET = new THREE.Color("#a99bff");
const AMBER = new THREE.Color("#ffb547");

const sstep = (a: number, b: number, t: number) => {
  const x = Math.min(1, Math.max(0, (t - a) / (b - a)));
  return x * x * (3 - 2 * x);
};
const ease = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

interface Data { brain: Brain; problem: ProblemData; naive: SolveData; qaoa: SolveData }

// ---------------------------------------------------------------- shaders
const RIM_VS = /* glsl */ `
varying vec3 vN; varying vec3 vV; varying vec3 vW;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vW = wp.xyz;
  vN = normalize(mat3(modelMatrix) * normal);
  vV = normalize(cameraPosition - wp.xyz);
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;
const RIM_FS = /* glsl */ `
uniform vec3 uColor; uniform float uPower; uniform float uIntensity; uniform float uFill;
uniform float uScan; uniform float uScanY; uniform float uScanW; uniform vec3 uScanColor;
varying vec3 vN; varying vec3 vV; varying vec3 vW;
void main() {
  float f = pow(1.0 - clamp(abs(dot(normalize(vN), normalize(vV))), 0.0, 1.0), uPower);
  float band = uScan * exp(-pow((vW.y - uScanY) / uScanW, 2.0));
  vec3 c = uColor * (f * uIntensity + uFill) + uScanColor * band * (0.5 + f);
  gl_FragColor = vec4(c, 1.0);
}`;

function rimMaterial(color: THREE.Color, intensity: number, power = 2.6, fill = 0, offset = -2) {
  return new THREE.ShaderMaterial({
    polygonOffset: true, polygonOffsetFactor: offset, polygonOffsetUnits: offset * 4,
    vertexShader: RIM_VS, fragmentShader: RIM_FS, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, toneMapped: false,
    uniforms: {
      uColor: { value: color.clone() }, uPower: { value: power }, uIntensity: { value: intensity },
      uFill: { value: fill }, uScan: { value: 0 }, uScanY: { value: 0 }, uScanW: { value: 4 },
      uScanColor: { value: CYAN.clone().multiplyScalar(1.6) },
    },
  });
}

function glowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  r.addColorStop(0, "rgba(255,255,255,1)");
  r.addColorStop(0.18, "rgba(255,255,255,0.85)");
  r.addColorStop(0.45, "rgba(255,255,255,0.22)");
  r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const GLOW = glowTexture();

function ringTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d")!;
  const r = g.createRadialGradient(128, 128, 70, 128, 128, 128);
  r.addColorStop(0, "rgba(255,255,255,0)");
  r.addColorStop(0.72, "rgba(255,255,255,0.0)");
  r.addColorStop(0.86, "rgba(255,255,255,1)");
  r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const RING = ringTexture();

function Shockwave({ at, color, start }: { at: Vec3; color: THREE.Color; start: number }) {
  const ref = useRef<THREE.Sprite>(null);
  useFrame(() => {
    const s = ref.current; if (!s) return;
    const x = (clock.t - start) / 1.3;
    const m = s.material as THREE.SpriteMaterial;
    if (x < 0 || x > 1) { m.opacity = 0; return; }
    const k = 10 + 150 * (1 - Math.pow(1 - x, 3));
    s.scale.set(k, k, 1);
    m.opacity = 0.9 * (1 - x);
  });
  return (
    <sprite ref={ref} position={at} renderOrder={22}>
      <spriteMaterial map={RING} color={color.clone().multiplyScalar(2)} transparent opacity={0}
                      depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
    </sprite>
  );
}

// ---------------------------------------------------------------- scene state over time
interface Frame {
  from: Float32Array | null; to: Float32Array | null; mix: number;  // map displacement
  field: Float32Array | null; fieldAmt: number;                    // error heatmap
  ghost: number;                                                   // old-map hologram
  scan: number; scanY: number;                                     // ultrasound sweep
  rot: number;                                                     // brain turn (rad)
  fade: number;                                                    // black overlay
}

function frameAt(t: number, d: Data, yMin: number, yMax: number): Frame {
  const f: Frame = { from: null, to: null, mix: 0, field: null, fieldAmt: 0, ghost: 0, scan: 0, scanY: 0, rot: 0, fade: 0 };
  const T = DUR[SCENE];
  if (SCENE === "hero") {
    f.rot = (t / T) * Math.PI * 2;
    const ph = (t % 6) / 6;                                         // two sweeps per loop, seamless
    f.scan = Math.sin(Math.PI * ph);
    f.scanY = yMax - (yMax - yMin) * ph;
    return f;
  }
  f.fade = 1 - sstep(0, 0.5, t) + sstep(T - 0.5, T, t);
  f.rot = 0.12 * Math.sin((t / T) * Math.PI * 2);
  if (SCENE === "shift") {
    f.ghost = sstep(0.2, 1.0, t);
    f.to = d.problem.trueShift; f.mix = ease(sstep(1.2, 3.8, t));
  } else if (SCENE === "bad") {
    f.to = d.naive.displacement; f.mix = ease(sstep(3.0, 5.4, t));
    f.field = d.naive.error; f.fieldAmt = sstep(3.4, 5.6, t);
  } else {
    f.from = d.naive.displacement; f.to = d.qaoa.displacement; f.mix = ease(sstep(3.6, 5.8, t));
    f.field = null; f.fieldAmt = 1;
  }
  return f;
}

// ---------------------------------------------------------------- brain
function BrainMesh({ d, bounds }: { d: Data; bounds: [number, number] }) {
  const { brain } = d;
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(brain.positions.slice(), 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(brain.n_vertices * 3), 3));
    g.setIndex(new THREE.BufferAttribute(brain.indices, 1));
    g.computeVertexNormals();
    return g;
  }, [brain]);
  const ghostGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(brain.positions.slice(), 3));
    g.setIndex(new THREE.BufferAttribute(brain.indices, 1));
    g.computeVertexNormals();
    return g;
  }, [brain]);
  const rim = useMemo(() => rimMaterial(new THREE.Color("#5aa8ff"), SCENE === "hero" ? 0.9 : 0.55, 3.0), []);
  const ghost = useMemo(() => rimMaterial(CYAN, 1.6, 1.4, 0.12, 6), []);
  const base = useMemo(() => new THREE.MeshPhysicalMaterial({
    vertexColors: true, roughness: 0.5, metalness: 0.0, clearcoat: 0.35, clearcoatRoughness: 0.4,
    sheen: 0.35, sheenColor: new THREE.Color("#9ccfff"), sheenRoughness: 0.6,
  }), []);
  const last = useRef({ mix: -1, key: "" });

  useFrame(() => {
    const f = frameAt(clock.t, d, bounds[0], bounds[1]);
    for (const m of [rim, ghost]) {
      m.uniforms.uScan.value = f.scan; m.uniforms.uScanY.value = f.scanY;
    }
    ghost.uniforms.uIntensity.value = 1.6 * f.ghost;
    ghost.uniforms.uFill.value = 0.12 * f.ghost;

    const key = `${f.mix.toFixed(4)}|${f.fieldAmt.toFixed(3)}`;
    if (key === last.current.key) return;
    last.current.key = key;

    // positions: preop + displacement (from -> to), exaggerated and capped like the app
    const p = (geo.getAttribute("position") as THREE.BufferAttribute).array as Float32Array;
    const b = brain.positions;
    const cap2 = CAP * CAP;
    for (let i = 0; i < p.length; i += 3) {
      const a0 = f.from ? f.from[i] : 0, a1 = f.from ? f.from[i + 1] : 0, a2 = f.from ? f.from[i + 2] : 0;
      const b0 = f.to ? f.to[i] : 0, b1 = f.to ? f.to[i + 1] : 0, b2 = f.to ? f.to[i + 2] : 0;
      let dx = (a0 + (b0 - a0) * f.mix) * SCALE, dy = (a1 + (b1 - a1) * f.mix) * SCALE, dz = (a2 + (b2 - a2) * f.mix) * SCALE;
      const m2 = dx * dx + dy * dy + dz * dz;
      if (m2 > cap2) { const k = CAP / Math.sqrt(m2); dx *= k; dy *= k; dz *= k; }
      p[i] = b[i] + dx; p[i + 1] = b[i + 1] + dy; p[i + 2] = b[i + 2] + dz;
    }
    geo.getAttribute("position").needsUpdate = true;
    geo.computeVertexNormals();

    // colours: pearl tissue, or the real error heatmap across the corrected region
    const col = (geo.getAttribute("color") as THREE.BufferAttribute).array as Float32Array;
    const w = d.problem.weight;
    const c = new THREE.Color();
    const fieldA = SCENE === "fix" ? d.naive.error : f.field;
    const fieldB = SCENE === "fix" ? d.qaoa.error : null;
    for (let i = 0; i < brain.n_vertices; i++) {
      const wi = w[i];
      c.copy(BASE).lerp(SITE, Math.min(1, wi * 0.8));
      if (fieldA && wi > 0.005) {
        const e = fieldB ? fieldA[i] + (fieldB[i] - fieldA[i]) * f.mix : fieldA[i];
        const r = Math.min(1, wi / 0.12);
        c.lerp(errorColor(e), r * r * (3 - 2 * r) * f.fieldAmt);
      }
      col[3 * i] = c.r; col[3 * i + 1] = c.g; col[3 * i + 2] = c.b;
    }
    geo.getAttribute("color").needsUpdate = true;
  });

  return (
    <>
      <mesh geometry={geo} material={base} />
      <mesh geometry={geo} material={rim} renderOrder={2} />
      {SCENE === "shift" && <mesh geometry={ghostGeo} material={ghost} renderOrder={3} />}
    </>
  );
}

// ---------------------------------------------------------------- landmarks and matches
function Glow({ at, color, size, opacity = 1 }: { at: Vec3; color: THREE.Color; size: number; opacity?: number }) {
  return (
    <sprite position={at} scale={[size, size, 1]} renderOrder={20}>
      <spriteMaterial map={GLOW} color={color.clone().multiplyScalar(2.2)} transparent opacity={opacity}
                      depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
    </sprite>
  );
}

type LineLook = { color: THREE.Color; opacity: number; width: number };

function Matches({ d }: { d: Data }) {
  const p = d.problem;
  const cands = p.candidates;
  const lines = useRef<any[]>([]);
  const dots = useRef<THREE.Sprite[]>([]);
  const mri = useRef<THREE.Sprite[]>([]);
  const ring = useRef<THREE.Sprite>(null);
  const naiveSel = d.naive.result.selection;
  const qSel = d.qaoa.result.selection;
  const samples = useMemo(() => [...d.qaoa.result.samples].reverse().map(s => s.bits), [d]);
  const suspect = d.naive.confidence.worst_candidate;

  useFrame(() => {
    const t = clock.t;
    const looks: LineLook[] = cands.map(() => ({ color: CYAN, opacity: 0, width: 1.5 }));
    let dotA = 0, mriA = 0, ringA = 0;
    if (SCENE === "hero") {
      mriA = 0.55 + 0.25 * Math.sin(t * 2.2);
    } else if (SCENE === "bad") {
      mriA = sstep(0.4, 1.0, t);
      dotA = sstep(0.8, 1.5, t);
      const on = sstep(1.5, 2.6, t);
      cands.forEach((c, i) => {
        const trusted = naiveSel[i] === 1;
        looks[i] = trusted
          ? { color: c.true ? new THREE.Color("#e8eef5") : RED, opacity: on, width: c.true ? 4 : 6.5 }
          : { color: new THREE.Color("#5d6b7a"), opacity: 0.35 * dotA, width: 2 };
        if (trusted && !c.true) looks[i].opacity = on * (0.75 + 0.25 * Math.sin(t * 9));
      });
      ringA = sstep(5.2, 5.8, t) * (0.55 + 0.45 * Math.sin(t * 6));
    } else if (SCENE === "fix") {
      mriA = 1; dotA = 1;
      if (t < 3.4) {
        // the solver's sampled answers flicker by, worst to best
        const k = Math.min(samples.length - 1, Math.floor((t / 3.4) * samples.length));
        const bits = samples[k];
        cands.forEach((_, i) => {
          looks[i] = bits[i] ? { color: CYAN, opacity: 0.95, width: 4.5 } : { color: new THREE.Color("#5d6b7a"), opacity: 0.3, width: 2 };
        });
      } else {
        const lock = sstep(3.4, 3.9, t);
        cands.forEach((_, i) => {
          looks[i] = qSel[i]
            ? { color: GREEN, opacity: 1, width: 4.5 + 2.5 * lock }
            : { color: RED, opacity: 0.7 * (1 - sstep(4.2, 5.2, t)), width: 2.5 };
        });
      }
    }
    lines.current.forEach((ln, i) => {
      if (!ln) return;
      const L = looks[i];
      ln.material.color.copy(L.color).multiplyScalar(1.8);
      ln.material.opacity = L.opacity;
      ln.material.linewidth = L.width;
      ln.visible = L.opacity > 0.01;
    });
    dots.current.forEach(s => { if (s) (s.material as THREE.SpriteMaterial).opacity = dotA; });
    mri.current.forEach(s => { if (s) (s.material as THREE.SpriteMaterial).opacity = mriA; });
    if (ring.current) {
      (ring.current.material as THREE.SpriteMaterial).opacity = ringA;
      const k = 22 + 6 * Math.sin(t * 6);
      ring.current.scale.set(k, k, 1);
    }
  });

  return (
    <group>
      {SCENE !== "shift" && p.landmarks.mri_used.map((q, i) => (
        <sprite key={`m${i}`} ref={el => { if (el) mri.current[i] = el; }} position={q} scale={[8, 8, 1]} renderOrder={20}>
          <spriteMaterial map={GLOW} color={VIOLET.clone().multiplyScalar(2.2)} transparent opacity={0}
                          depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
        </sprite>
      ))}
      {(SCENE === "bad" || SCENE === "fix") && cands.map((c, i) => (
        <group key={c.id}>
          <sprite ref={el => { if (el) dots.current[i] = el; }} position={c.pos} scale={[7, 7, 1]} renderOrder={20}>
            <spriteMaterial map={GLOW} color={CYAN.clone().multiplyScalar(2)} transparent opacity={0}
                            depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
          </sprite>
          <Line ref={(el: any) => { if (el) lines.current[i] = el; }} points={[p.landmarks.mri_used[c.landmark], c.pos]}
                color="#ffffff" lineWidth={2} transparent opacity={0} depthTest={false} renderOrder={19} toneMapped={false} />
        </group>
      ))}
      {SCENE === "bad" && <Shockwave at={p.placement.site} color={RED} start={4.2} />}
      {SCENE === "fix" && <Shockwave at={p.placement.site} color={GREEN} start={3.45} />}
      {SCENE === "fix" && <Shockwave at={p.placement.site} color={GREEN} start={3.75} />}
      {SCENE === "bad" && suspect !== null && (
        <sprite ref={ring} position={cands[suspect].pos} scale={[22, 22, 1]} renderOrder={21}>
          <spriteMaterial map={GLOW} color={AMBER.clone().multiplyScalar(1.6)} transparent opacity={0}
                          depthTest={false} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
        </sprite>
      )}
    </group>
  );
}

// ---------------------------------------------------------------- atmosphere
function Dust({ center }: { center: THREE.Vector3 }) {
  const ref = useRef<THREE.Points>(null);
  const geo = useMemo(() => {
    let seed = 7;
    const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
    const n = 700, arr = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 130 + rnd() * 260, a = rnd() * Math.PI * 2, b = Math.acos(2 * rnd() - 1);
      arr.set([r * Math.sin(b) * Math.cos(a), r * Math.cos(b) * 0.6, r * Math.sin(b) * Math.sin(a)], i * 3);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    return g;
  }, []);
  const mat = useMemo(() => new THREE.PointsMaterial({
    color: new THREE.Color("#9fd4ff"), size: 1.6, transparent: true, opacity: 0.5, depthWrite: false,
    blending: THREE.AdditiveBlending, sizeAttenuation: true,
  }), []);
  useFrame(() => { if (ref.current) ref.current.rotation.y = (clock.t / DUR[SCENE]) * Math.PI * 0.5; });
  return <points ref={ref} geometry={geo} material={mat} position={center} />;
}

function Orbit({ center, r, tilt, speed, opacity }: { center: THREE.Vector3; r: number; tilt: number; speed: number; opacity: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(() => { if (ref.current) ref.current.rotation.set(Math.PI / 2 + tilt, 0, (clock.t / DUR[SCENE]) * Math.PI * 2 * speed); });
  return (
    <mesh ref={ref} position={center}>
      <torusGeometry args={[r, 0.35, 6, 220]} />
      <meshBasicMaterial color="#8fc8ff" transparent opacity={opacity} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

// ---------------------------------------------------------------- camera + clock
function Rig({ d, center }: { d: Data; center: THREE.Vector3 }) {
  const { camera } = useThree();
  const site = useMemo(() => new THREE.Vector3(...d.problem.placement.site), [d]);
  const n = useMemo(() => new THREE.Vector3(...d.problem.placement.normal).normalize(), [d]);
  useFrame(() => {
    const t = clock.t, T = DUR[SCENE];
    if (SCENE === "hero") {
      camera.position.set(center.x + 30, center.y + 60, center.z + 375);
      camera.lookAt(center.x, center.y - 4, center.z);
      return;
    }
    const lat = new THREE.Vector3(Math.sign(site.x) || 1, 0, 0);
    const dir = n.clone().multiplyScalar(0.5).add(lat.multiplyScalar(0.8)).add(new THREE.Vector3(0, 0.12, 0.25)).normalize();
    const look = site.clone().multiplyScalar(0.6).add(center.clone().multiplyScalar(0.4));
    const dist = 440 - 50 * ease(Math.min(1, t / T));                 // slow push-in
    const sway = 0.14 * Math.sin((t / T) * Math.PI * 2);
    dir.applyAxisAngle(new THREE.Vector3(0, 1, 0), sway);
    camera.position.copy(look).addScaledVector(dir, dist);
    camera.lookAt(look);
    camera.updateMatrixWorld();
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    camera.position.addScaledVector(right, -dist * 0.09);           // brain sits right of centre
    camera.lookAt(look.clone().addScaledVector(right, -dist * 0.09));
  }, -1);
  return null;
}

function Clock({ onFrame }: { onFrame: (t: number) => void }) {
  const advance = useThree(s => s.advance);
  useEffect(() => {
    if (!CAPTURE) return;
    (window as any).__render = (t: number) => { clock.t = t; advance(performance.now()); onFrame(t); return true; };
    (window as any).__duration = DUR[SCENE];
  }, [advance, onFrame]);
  useFrame(s => {
    if (CAPTURE) return;
    clock.t = s.clock.elapsedTime % DUR[SCENE];
    onFrame(clock.t);
  }, -2);
  return null;
}

function Spin({ rotOf, center, children }: { rotOf: () => number; center: THREE.Vector3; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  useFrame(() => { if (ref.current) ref.current.rotation.y = rotOf(); }, -1);
  return (
    <group position={center}>
      <group ref={ref}>
        <group position={center.clone().negate()}>{children}</group>
      </group>
    </group>
  );
}

// ---------------------------------------------------------------- page
export default function Film() {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fadeRef = useRef<HTMLDivElement>(null);
  const readRef = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      const [brain, problem] = await Promise.all([api.brain(), api.problem(DEMO)]);
      const [naive, qaoa] = await Promise.all([api.solve(problem.problem_id, "naive"), api.solve(problem.problem_id, "qaoa")]);
      setD({ brain, problem, naive, qaoa });
    })().catch(e => setErr(String(e)));
  }, []);

  const geom = useMemo(() => {
    if (!d) return null;
    const b = d.brain.positions;
    let y0 = Infinity, y1 = -Infinity;
    const c = new THREE.Vector3();
    for (let i = 0; i < b.length; i += 3) {
      c.x += b[i]; c.y += b[i + 1]; c.z += b[i + 2];
      y0 = Math.min(y0, b[i + 1]); y1 = Math.max(y1, b[i + 1]);
    }
    c.multiplyScalar(3 / b.length);
    return { center: c, bounds: [y0, y1] as [number, number] };
  }, [d]);

  const onFrame = useMemo(() => (t: number) => {
    if (!d || !geom) return;
    const f = frameAt(t, d, geom.bounds[0], geom.bounds[1]);
    if (fadeRef.current) fadeRef.current.style.opacity = String(f.fade);
    const r = readRef.current, s = subRef.current;
    if (!r || !s) return;
    const show = (x: number) => { r.style.opacity = String(x); s.style.opacity = String(x); };
    if (SCENE === "shift") {
      const mm = d.problem.metrics.tre_uncorrected * f.mix;
      r.textContent = `${mm.toFixed(1)} mm`;
      r.style.color = "#ff8a80";
      s.textContent = "how far off the map is";
      show(sstep(1.2, 1.8, t));
    } else if (SCENE === "bad") {
      r.textContent = `${d.naive.evaluation.tre.toFixed(1)} mm`;
      r.style.color = "#ff8a80";
      s.textContent = "still off, after trusting every clue";
      show(sstep(5.0, 5.6, t));
    } else if (SCENE === "fix") {
      const v = d.naive.evaluation.tre + (d.qaoa.evaluation.tre - d.naive.evaluation.tre) * f.mix;
      r.textContent = `${v.toFixed(1)} mm`;
      r.style.color = f.mix > 0.6 ? "#7ff0c0" : "#ff8a80";
      s.textContent = f.mix > 0.6 ? "off, using only the clues that agree" : "choosing which clues to trust";
      show(sstep(0.6, 1.2, t));
    } else show(0);
  }, [d, geom]);

  return (
    <div style={{ position: "fixed", inset: 0, background: "#06080b" }}>
      {d && geom && (
        <Canvas frameloop={CAPTURE ? "never" : "always"} dpr={1}
                camera={{ fov: 30, near: 1, far: 4000, position: [0, 0, 500] }}
                gl={{ antialias: false, preserveDrawingBuffer: true }}
                onCreated={({ gl }) => { gl.toneMapping = THREE.ACESFilmicToneMapping; gl.toneMappingExposure = 1.05; }}>
          <color attach="background" args={["#06080b"]} />
          <hemisphereLight args={["#eef2f7", "#10151c", 0.45]} />
          <directionalLight position={[160, 260, 220]} intensity={1.55} color="#fff4e6" />
          <directionalLight position={[-260, 60, 120]} intensity={0.55} color="#cfe0ff" />
          <directionalLight position={[-120, 120, -300]} intensity={2.0} color="#5fb4ff" />
          <directionalLight position={[240, -40, -260]} intensity={1.4} color="#a99bff" />
          <Spin center={geom.center} rotOf={() => frameAt(clock.t, d, geom.bounds[0], geom.bounds[1]).rot}>
            <BrainMesh d={d} bounds={geom.bounds} />
            <Matches d={d} />
          </Spin>
          {SCENE === "hero" && (
            <>
              <Dust center={geom.center} />
              <Orbit center={geom.center} r={150} tilt={0.32} speed={0.25} opacity={0.13} />
              <Orbit center={geom.center} r={182} tilt={-0.42} speed={-0.15} opacity={0.07} />
            </>
          )}
          {SCENE === "shift" && <Dust center={geom.center} />}
          <Rig d={d} center={geom.center} />
          <Clock onFrame={onFrame} />
          <EffectComposer multisampling={0}>
            <Bloom intensity={1.15} luminanceThreshold={0.62} luminanceSmoothing={0.25} mipmapBlur radius={0.7} />
            <Vignette offset={0.28} darkness={0.75} />
            <SMAA />
          </EffectComposer>
        </Canvas>
      )}
      <div style={{ position: "absolute", left: 72, top: 64, fontFamily: "'Space Grotesk', sans-serif" }}>
        <div ref={readRef} style={{ fontSize: 96, fontWeight: 600, lineHeight: 1, opacity: 0, letterSpacing: -1 }} />
        <div ref={subRef} style={{ fontFamily: "Inter, sans-serif", fontSize: 30, color: "#b8c4cf", marginTop: 14, opacity: 0 }} />
      </div>
      {SCENE !== "hero" && (
        <div style={{ position: "absolute", right: 64, bottom: 48, fontFamily: "Inter, sans-serif", fontSize: 20, color: "#6f7d8a" }}>
          Real patient (RESECT Case 12) · movement shown {SCALE}× for visibility
        </div>
      )}
      {SCENE === "shift" && (
        <div style={{ position: "absolute", left: 72, bottom: 48, fontFamily: "Inter, sans-serif", fontSize: 24, color: "#9fe6ff" }}>
          <span style={{ color: "#5fd8ff" }}>Glow</span> = where the real brain has moved away from the MRI map
        </div>
      )}
      <div ref={fadeRef} style={{ position: "absolute", inset: 0, background: "#06080b", opacity: 0, pointerEvents: "none" }} />
      {err && <div style={{ position: "absolute", left: 24, top: 24, color: "#ff8a80", fontFamily: "monospace" }}>{err}</div>}
      {d && <div id="film-ready" style={{ display: "none" }} />}
    </div>
  );
}
