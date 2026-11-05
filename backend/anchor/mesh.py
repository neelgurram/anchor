"""L6 — 3D brain for DISPLAY ONLY.

All error numbers are computed in native patient millimetres (registration.py). This
module only turns those warps into something you can see:

  * Template brain: fsaverage6 pial surface (MRI-derived), copied from Continuum.
  * Scene frame: x = patient left, y = superior, z = anterior (mm). RESECT landmarks are in
    scanner RAS; ras_to_scene is a proper rotation (no mirroring), so shift directions stay true.
  * Placement: each patient's landmark cluster is translated (never rotated or scaled) to
    sit ~12 mm under the template surface at the point whose outward normal opposes the
    mean shift — i.e. where a craniotomy would let the brain sink in that direction.
  * Displacement on the surface = the warp's field, faded out smoothly away from the
    landmarks so distant cortex does not drift.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .data import ROOT, Case
from .registration import Warp

TEMPLATE = ROOT / "data" / "template"
DEPTH_MM = 12.0
FADE_IN, FADE_OUT = 18.0, 50.0   # full field within 18 mm of a landmark, zero beyond 50 mm
# A spline pulled through a wrong match can extrapolate to absurd values on far cortex.
# The DISPLAY clips each vertex at this length (the UI says so); metrics are never clipped.
DISPLAY_CLIP_MM = 30.0


def ras_to_scene(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    return np.stack([-p[..., 0], p[..., 2], p[..., 1]], -1)


def scene_to_ras(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, float)
    return np.stack([-q[..., 0], q[..., 2], q[..., 1]], -1)


@dataclass
class Template:
    pos: np.ndarray        # (V, 3) scene mm
    idx: np.ndarray        # (F, 3)
    region: np.ndarray     # (V,)
    normals: np.ndarray    # (V, 3)
    vpos: np.ndarray       # ventricles
    vidx: np.ndarray
    meta: dict


def _vertex_normals(pos: np.ndarray, idx: np.ndarray) -> np.ndarray:
    a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    fn = np.cross(b - a, c - a)
    n = np.zeros_like(pos)
    for k in range(3):
        np.add.at(n, idx[:, k], fn)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    # orient outward
    if np.mean(np.einsum("ij,ij->i", n, pos - pos.mean(0))) < 0:
        n = -n
    return n


@lru_cache(maxsize=1)
def template() -> Template:
    d = np.load(TEMPLATE / "brain.npz")
    pos = d["brain_pos"].astype(float)
    idx = d["brain_idx"].astype(np.int64)
    meta = json.loads((TEMPLATE / "brain_meta.json").read_text())
    return Template(pos, idx, d["brain_region"].astype(int), _vertex_normals(pos, idx),
                    d["ventricles_pos"].astype(float), d["ventricles_idx"].astype(np.int64), meta)


@dataclass
class Placement:
    offset: np.ndarray       # scene = ras_to_scene(patient) + offset
    site_vertex: int
    site: np.ndarray         # craniotomy centre on the template surface (scene mm)
    normal: np.ndarray

    def to_scene(self, p_ras: np.ndarray) -> np.ndarray:
        return ras_to_scene(p_ras) + self.offset

    def to_patient(self, q_scene: np.ndarray) -> np.ndarray:
        return scene_to_ras(np.asarray(q_scene, float) - self.offset)


@lru_cache(maxsize=64)
def _placement_cached(case_id: str, key: bytes) -> Placement:
    mri, us = np.frombuffer(key, dtype=float).reshape(2, -1, 3)
    t = template()
    s = ras_to_scene(us.mean(0) - mri.mean(0))
    s_dir = s / (np.linalg.norm(s) + 1e-12)
    # the brain sinks AWAY from the opening: craniotomy normal ≈ -shift direction.
    # Prefer upper-lateral cortex (no openings through the skull base).
    score = t.normals @ (-s_dir) + 0.25 * (t.pos[:, 1] > 0)
    v = int(np.argmax(score))
    target = t.pos[v] - t.normals[v] * DEPTH_MM
    offset = target - ras_to_scene(mri.mean(0))
    return Placement(offset, v, t.pos[v], t.normals[v])


def placement(case: Case) -> Placement:
    key = np.ascontiguousarray(np.stack([case.mri, case.us]), float).tobytes()
    return _placement_cached(case.case_id, key)


def fade(case: Case, pl: Placement, pts_scene: np.ndarray) -> np.ndarray:
    lm = pl.to_scene(case.mri)
    d = np.sqrt(((pts_scene[:, None, :] - lm[None]) ** 2).sum(-1)).min(1)
    t = np.clip((d - FADE_IN) / (FADE_OUT - FADE_IN), 0, 1)
    return 0.5 * (1 + np.cos(np.pi * t))           # 1 near landmarks -> 0 far away


def surface_displacement(case: Case, pl: Placement, warp: Warp, weight: np.ndarray | None = None) -> np.ndarray:
    """Per-vertex displacement in SCENE mm for the template surface."""
    t = template()
    w = fade(case, pl, t.pos) if weight is None else weight
    out = np.zeros_like(t.pos)
    near = w > 1e-4
    if warp.kind == "identity" or not near.any():
        return out
    d_ras = warp.displacement(pl.to_patient(t.pos[near]))
    out[near] = ras_to_scene(d_ras) * w[near, None]  # vectors: rotation only, no offset
    return out


def clip_for_display(disp: np.ndarray, limit: float = DISPLAY_CLIP_MM) -> tuple[np.ndarray, float]:
    """Clip per-vertex displacement length for drawing. Returns (clipped, fraction clipped)."""
    n = np.linalg.norm(disp, axis=1)
    over = n > limit
    out = disp.copy()
    out[over] *= (limit / n[over])[:, None]
    return out, float(over.mean())


def b64(arr: np.ndarray, dtype=np.float32) -> str:
    return base64.b64encode(np.ascontiguousarray(arr, dtype=dtype).tobytes()).decode("ascii")
