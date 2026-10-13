// Shared look. Frozen by docs/CONTRACT.md section 5.
export const THEME = {
  bg: '#0B0D10', plinth: '#D9D9D6', building: '#F2F2EE', cyan: '#6FE7FF', amber: '#FFB347',
  red: '#FF4D4D', cardOrange: '#FF8A3D', cardBgTop: '#0a1018', cardBgBottom: '#14202c',
  circleField: '#e6e6e4', circleInk: '#0a0a0a', citizenKey: '#FFC89A', systemKey: '#E6EEFF',
  mono: '"JetBrains Mono","IBM Plex Mono",Consolas,monospace',
  condensed: '"Barlow Condensed","Roboto Condensed","Arial Narrow",sans-serif',
};

const STOPS = [
  [0.0, [242, 242, 238]],
  [0.5, [255, 179, 71]],
  [1.0, [255, 77, 77]],
];

// white -> amber -> red
export function riskColor(deviation_risk) {
  const v = Math.max(0, Math.min(1, Number(deviation_risk) || 0));
  let a = STOPS[0], b = STOPS[1];
  if (v > 0.5) { a = STOPS[1]; b = STOPS[2]; }
  const t = (v - a[0]) / (b[0] - a[0]);
  const c = a[1].map((x, i) => Math.round(x + (b[1][i] - x) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
