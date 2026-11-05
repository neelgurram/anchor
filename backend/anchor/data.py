"""L0 — patient landmark data.

RESECT (Xiao et al., Medical Physics 44(7), 2017; DOI 10.11582/2017.00004; CC BY 4.0):
22 low-grade-glioma cases, each with ~15 expert landmark pairs between the pre-operative
MRI and the intra-operative ultrasound acquired after the skull was opened but before
resection. The difference between the two is real, measured brain shift (plus residual
tracking error), in world millimetres.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESECT_DIR = ROOT / "data" / "resect"
_ROW = re.compile(r"^\s*(-?[\d.eE+-]+\s+){5}-?[\d.eE+-]+")


@dataclass(frozen=True)
class Case:
    case_id: str          # e.g. "Case1"
    mri: np.ndarray       # (N, 3) landmark positions in the pre-op MRI, mm
    us: np.ndarray        # (N, 3) the same landmarks in the intra-op ultrasound, mm

    @property
    def n(self) -> int:
        return len(self.mri)

    @property
    def shift(self) -> np.ndarray:
        """Per-landmark displacement MRI -> ultrasound (mm)."""
        return self.us - self.mri

    @property
    def shift_mm(self) -> np.ndarray:
        return np.linalg.norm(self.shift, axis=1)


def parse_tag(text: str) -> tuple[np.ndarray, np.ndarray]:
    """Parse an MNI tag point file. Each data row: x1 y1 z1 x2 y2 z2 [label]."""
    if not text.lstrip().startswith("MNI Tag Point File"):
        raise ValueError("not an MNI tag point file")
    body = text.split("Points", 1)[1].split("=", 1)[1]
    rows = []
    for line in body.splitlines():
        line = line.split('"', 1)[0].replace(";", " ")
        if _ROW.match(line):
            rows.append([float(v) for v in line.split()[:6]])
    if not rows:
        raise ValueError("tag file has no points")
    arr = np.asarray(rows, dtype=float)
    return arr[:, :3], arr[:, 3:6]


def load_case(case_id: str, directory: pathlib.Path = RESECT_DIR) -> Case:
    path = directory / f"{case_id}-MRI-beforeUS.tag"
    mri, us = parse_tag(path.read_text())
    return Case(case_id, mri, us)


def list_cases(directory: pathlib.Path = RESECT_DIR) -> list[str]:
    ids = [p.name.split("-")[0] for p in directory.glob("Case*-MRI-beforeUS.tag")]
    return sorted(ids, key=lambda s: int(s[4:]))


def load_all(directory: pathlib.Path = RESECT_DIR) -> list[Case]:
    return [load_case(c, directory) for c in list_cases(directory)]
