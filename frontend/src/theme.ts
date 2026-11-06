import * as THREE from "three";

export const COLORS = {
  bg: "#06080b",
  accent: "#19d3c5",
  mri: "#9b8cff",
  us: "#4cc9f0",
  kept: "#3ddc97",
  rejected: "#ff5d6c",
  held: "#f4f6f8",
  warn: "#ffb547",
};

// Error colormap (mm), same anchors as Continuum: blue < 1 mm, cyan, yellow 3 mm, red > 5 mm.
export const ERROR_STOPS = [
  { mm: 0, hex: "#2b6cff" },
  { mm: 1, hex: "#19d3c5" },
  { mm: 3, hex: "#ffe14d" },
  { mm: 5, hex: "#ff3b3b" },
];
const STOP_COLORS = ERROR_STOPS.map(s => new THREE.Color(s.hex));
const tmp = new THREE.Color();

export function errorColor(mm: number): THREE.Color {
  if (mm <= ERROR_STOPS[0].mm) return tmp.copy(STOP_COLORS[0]);
  for (let i = 1; i < ERROR_STOPS.length; i++) {
    if (mm <= ERROR_STOPS[i].mm) {
      const t = (mm - ERROR_STOPS[i - 1].mm) / (ERROR_STOPS[i].mm - ERROR_STOPS[i - 1].mm);
      return tmp.copy(STOP_COLORS[i - 1]).lerp(STOP_COLORS[i], t);
    }
  }
  return tmp.copy(STOP_COLORS[STOP_COLORS.length - 1]);
}
