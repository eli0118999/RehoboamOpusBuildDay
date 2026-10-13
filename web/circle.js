// Mini Rehoboam - the eclipse "prediction circle" (2D Canvas, no dependencies).
//
// Pale field + pale disc (a hole), black ink only. Severity 0 = a single hairline ring;
// ~0.2-0.45 = state B (thin ring, fibrous spikes); ~0.45-0.7 = state A (thick smoky ring);
// >=0.7 = state C (black crescent behind a pale disc shoved right, radial streaks, inward bleed).
//
// Rendering: the expensive ink (blurred ring body, crescent, particles, strands, spikes) is drawn
// into an offscreen "cache" canvas at view rotation 0 and only rebuilt when the (interpolated)
// model changes. Per frame we fill the field, blit the cache (rotated for focus), draw a few
// drifting particles and the labels. The loop runs at ~30fps and pauses when the tab is hidden.

const FIELD = '#e6e6e4';
const FIELD_C = '#f4f4f2';
const INK = '#0a0a0a';
const SANS = '"Barlow Condensed","Roboto Condensed","Arial Narrow",sans-serif';
const MONO = '"JetBrains Mono","IBM Plex Mono",Consolas,monospace';
const D2R = Math.PI / 180;
const TRANSITION_MS = 1200;

// ---------- small helpers ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeIO = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const wrap180 = (d) => ((((d + 180) % 360) + 360) % 360) - 180;
const wrap360 = (d) => ((d % 360) + 360) % 360;

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function rngFor(seed) {
  let a = seed >>> 0;
  const r = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  r.gauss = () => {
    let u = 0, v = 0;
    while (u === 0) u = r();
    v = r();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  return r;
}
const clean = (s) => String(s == null ? '' : s).replace(/Â/g, '');

function lerpColor(a, b, t) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return 'rgb(' + pa.map((v, i) => Math.round(lerp(v, pb[i], t))).join(',') + ')';
}

// ---------- model (what gets interpolated) ----------
function buildModel(state) {
  const divs = (state && state.divergences) || [];
  const flares = divs.map((d) => ({
    id: d.divergence_id, angle: d.angle_deg, spread: d.arc_spread_deg,
    out: d.outward, inn: d.inward, sev: d.severity,
  }));
  const polar = (state && state.geo && state.geo.resident_polar) || {};
  const bg = ((state && state.resident_states) || []).filter((rs) => polar[rs.resident_id])
    .map((rs) => ({ id: rs.resident_id, angle: polar[rs.resident_id][0], v: rs.variance || 0 }));
  return {
    flares, bg, rot: (state && state.ring_rotation_deg) || 0,
    sev: flares.reduce((m, f) => Math.max(m, f.sev), 0), inn: flares.reduce((m, f) => Math.max(m, f.inn), 0),
  };
}
function zeroed(f) { return { id: f.id, angle: f.angle, spread: f.spread, out: 0, inn: 0, sev: 0 }; }
function interpModel(a, b, t) {
  const out = { flares: [], bg: [], rot: lerp(a.rot, b.rot, t) };
  const am = new Map(a.flares.map((f) => [f.id, f]));
  const bm = new Map(b.flares.map((f) => [f.id, f]));
  const ids = new Set([...am.keys(), ...bm.keys()]);
  for (const id of ids) {
    const fa = am.get(id) || zeroed(bm.get(id));
    const fb = bm.get(id) || zeroed(am.get(id));
    out.flares.push({
      id, angle: wrap360(fa.angle + wrap180(fb.angle - fa.angle) * t),
      spread: lerp(fa.spread, fb.spread, t), out: lerp(fa.out, fb.out, t),
      inn: lerp(fa.inn, fb.inn, t), sev: lerp(fa.sev, fb.sev, t),
    });
  }
  const bgA = new Map(a.bg.map((x) => [x.id, x]));
  for (const x of b.bg) {
    const p = bgA.get(x.id);
    out.bg.push({ id: x.id, angle: x.angle, v: p ? lerp(p.v, x.v, t) : x.v });
  }
  out.sev = out.flares.reduce((m, f) => Math.max(m, f.sev), 0);
  out.inn = out.flares.reduce((m, f) => Math.max(m, f.inn), 0);
  return out;
}

// ---------- labels ----------
const STATUS = {
  analysis_required: 'ANALYSIS REQUIRED:', divergence: 'DIVERGENCE:',
  elevated_scrutiny: 'ELEVATED SCRUTINY:', special_circumstances: 'SPECIAL CIRCUMSTANCES:',
};
function labelFromDivergence(d) {
  const small = [];
  if (d.spread_label) small.push(clean(d.spread_label).toUpperCase());
  else if (d.status === 'special_circumstances') small.push('INTERVENTION IN PROGRESS');
  small.push((d.status === 'special_circumstances' ? 'LOCATION: ' : 'FOCAL POINT: ') + clean(d.focal_coords).toUpperCase());
  return {
    key: d.divergence_id, status: STATUS[d.status] || 'DIVERGENCE:', place: clean(d.place_label).toUpperCase(),
    small, angle: d.angle_deg, sev: d.severity,
  };
}

// ======================================================================
export function createCircle(canvasEl, { onSelect } = {}) {
  const ctx = canvasEl.getContext('2d');
  const mk = () => document.createElement('canvas');
  const cache = mk(), smoke = mk(), cres = mk(), fine = mk(), inner = mk();
  const cctx = cache.getContext('2d'), sctx = smoke.getContext('2d'), rctx = cres.getContext('2d'),
    fctx = fine.getContext('2d'), ictx = inner.getContext('2d');
  const hasFilter = typeof ctx.filter === 'string';
  const tmp = mk(), tctx = tmp.getContext('2d');

  let W = 400, H = 400, dpr = 1, S = 400, U = 1, R = 120, cx = 200, cy = 200;
  let state = null, view = 'system';
  let from = buildModel({}), to = buildModel({}), shown = from;
  let tStart = 0, transitioning = false, dirty = true;
  let viewRot = 0, viewRotTarget = 0, focusRid = null;
  let label = null, prevLabel = null, labelT = 1;
  let breath = [];
  let lastFrame = 0, raf = 0, running = false;
  let crescentW = 0; // current crescent weight (for field + centre shift)
  let rx = 200;

  // ---- blur compositing ----
  function blurDraw(dst, src, px, alpha = 1) {
    dst.save();
    dst.globalAlpha = alpha;
    if (hasFilter) {
      dst.filter = 'blur(' + px.toFixed(2) + 'px)';
      dst.drawImage(src, 0, 0);
    } else { // cheap fallback: down/up-sample
      const k = 1 / (1 + px / 1.5);
      tmp.width = Math.max(2, Math.round(W * k)); tmp.height = Math.max(2, Math.round(H * k));
      tctx.imageSmoothingEnabled = true;
      tctx.drawImage(src, 0, 0, tmp.width, tmp.height);
      dst.imageSmoothingEnabled = true;
      dst.drawImage(tmp, 0, 0, W, H);
    }
    dst.restore();
  }
  const clear = (c) => { c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, H); c.globalCompositeOperation = 'source-over'; c.filter = 'none'; c.globalAlpha = 1; };
  const pt = (bearing, rho, ox = rx) => {
    const a = bearing * D2R;
    return [ox + Math.sin(a) * rho, cy - Math.cos(a) * rho];
  };

  // ---- ink noise: its phase is the "clock" (ring_rotation_deg) ----
  function noiseAt(bearing, rot) {
    const t = (bearing - rot * 3) * D2R;
    return 0.5 + 0.5 * (0.5 * Math.sin(3 * t + 1.3) + 0.3 * Math.sin(7 * t + 4.1) + 0.2 * Math.sin(13 * t + 2.2));
  }
  const leftWeight = (bearing) => 0.5 + 0.5 * Math.cos((bearing - 235) * D2R); // heavier bottom-left

  // ---- the main build ----
  function rebuild(m) {
    const sev = m.sev;
    const c = smooth(0.62, 0.86, sev);
    crescentW = c;
    const bB = smooth(0.04, 0.3, sev) * (1 - 0.5 * smooth(0.45, 0.6, sev));
    const bA = smooth(0.38, 0.58, sev);
    const gain = smooth(0, 0.25, sev);
    rx = cx + c * 0.045 * S;
    cy = H / 2 - c * 0.04 * S;
    const rot = m.rot;

    clear(cctx); clear(sctx); clear(rctx); clear(fctx); clear(ictx);
    breath = [];
    if (sev <= 0.004 && m.flares.every((f) => f.out < 0.01)) return; // perfect: hairline only

    // ---- ring width profile ----
    const widthAt = (b) => {
      let w = bB * 2.6 * U + bA * U * (1.8 + 5.2 * leftWeight(b) * (0.35 + 0.65 * noiseAt(b, rot))) + c * 2.4 * U;
      w *= 0.75 + 0.5 * noiseAt(b * 1.7 + 40, rot);
      for (const f of m.flares) {
        const sg = f.spread * 1.1 + 7;
        const d = wrap180(b - f.angle);
        w += f.sev * f.out * 5 * U * Math.exp(-(d * d) / (2 * sg * sg));
      }
      return w;
    };

    // ---- smoke layer: ring body + blotches ----
    const N = 720;
    const jr = rngFor(1234);
    sctx.fillStyle = INK;
    sctx.globalAlpha = 0.95;
    sctx.beginPath();
    const ws = [];
    for (let i = 0; i < N; i++) ws.push(widthAt((i / N) * 360));
    for (let i = 0; i <= N; i++) {
      const b = (i / N) * 360, w = ws[i % N];
      const [x, y] = pt(b, R + w * 0.55);
      i ? sctx.lineTo(x, y) : sctx.moveTo(x, y);
    }
    for (let i = N; i >= 0; i--) {
      const b = (i / N) * 360, w = ws[i % N];
      const [x, y] = pt(b, R - w * 0.45);
      sctx.lineTo(x, y);
    }
    sctx.fill();
    // smoky blotches around the ring (A / C thick, B light)
    const blobAmt = clamp(bA + c * 0.8 + bB * 0.25, 0, 1.4);
    const nb = Math.floor(1700 * blobAmt);
    for (let i = 0; i < nb; i++) {
      let b;
      for (let k = 0; k < 6; k++) { b = jr() * 360; if (jr() < leftWeight(b) * (0.5 + noiseAt(b + 90, rot)) ) break; }
      const w = widthAt(b);
      const off = jr.gauss() * (w * 0.45 + 1.2 * U);
      const [x, y] = pt(b, R + off + (jr() < 0.5 ? 0 : w * 0.15));
      sctx.globalAlpha = 0.05 + jr() * 0.13;
      sctx.beginPath();
      sctx.arc(x, y, (0.8 + jr() * 3.2) * U * (0.6 + bA), 0, 6.283);
      sctx.fill();
    }
    // local flare smoke clouds
    for (const f of m.flares) {
      if (f.out < 0.02) continue;
      const r = rngFor(hash(f.id) ^ 77);
      const n = Math.floor(260 * f.out * (0.4 + f.sev));
      const sg = f.spread * 0.9 + 6;
      for (let i = 0; i < n; i++) {
        const b = f.angle + r.gauss() * sg;
        const d = Math.abs(r.gauss()) * R * 0.05 * f.out * (1 + f.sev);
        const [x, y] = pt(b, R + d);
        sctx.globalAlpha = 0.06 + r() * 0.1;
        sctx.beginPath();
        sctx.arc(x, y, (0.7 + r() * 2.2) * U, 0, 6.283);
        sctx.fill();
      }
    }

    // ---- crescent layer: second black disc offset left ----
    if (c > 0.002) {
      const dx = c * 0.3 * R, Rb = R * 1.03;
      const bx = rx - dx;
      const g = rctx.createRadialGradient(bx, cy, Rb * 0.55, bx, cy, Rb * 1.02);
      g.addColorStop(0, 'rgba(10,10,10,1)');
      g.addColorStop(0.8, 'rgba(10,10,10,0.97)');
      g.addColorStop(1, 'rgba(10,10,10,0.8)');
      rctx.fillStyle = g;
      rctx.globalAlpha = clamp(c * 1.2);
      rctx.beginPath(); rctx.arc(bx, cy, Rb, 0, 6.283); rctx.fill();
      // ragged smoky outer edge
      const rr = rngFor(555);
      rctx.fillStyle = INK;
      for (let i = 0; i < 1500 * c; i++) {
        const ang = Math.PI + rr.gauss() * 1.0; // canvas angle, left-weighted (0 = right)
        const rad = Rb + Math.abs(rr.gauss()) * R * 0.07 * (0.5 + noiseAt(ang / D2R, rot));
        rctx.globalAlpha = 0.04 + rr() * 0.12;
        rctx.beginPath();
        rctx.arc(bx + Math.cos(ang) * rad, cy + Math.sin(ang) * rad, (1.5 + rr() * 5) * U, 0, 6.283);
        rctx.fill();
      }
    }

    // ---- fine layer: corona particles, strands, streaks ----
    fctx.fillStyle = INK; fctx.strokeStyle = INK; fctx.lineCap = 'round';
    for (const f of m.flares) {
      if (f.out < 0.015) continue;
      const r = rngFor(hash(f.id) ^ 991);
      const sg = 6 + f.spread * 1.1;
      const reach = R * 0.36 * f.out;
      const n = Math.floor(1700 * f.out * (0.35 + 0.65 * Math.min(1, 0.35 + f.spread / 9)));
      for (let i = 0; i < n; i++) {
        const b = f.angle + r.gauss() * sg;
        const d = reach * Math.pow(r(), 2.1) + widthAt(b) * 0.4;
        const [x, y] = pt(b, R + d);
        fctx.globalAlpha = 0.3 + r() * 0.6;
        fctx.beginPath();
        fctx.arc(x, y, (0.3 + r() * 0.55) * U, 0, 6.283);
        fctx.fill();
      }
      const ns = Math.floor(n / 9);
      for (let i = 0; i < ns; i++) {
        const b = f.angle + r.gauss() * sg * 0.9;
        const d0 = widthAt(b) * 0.3;
        const d1 = R * 0.04 + reach * Math.pow(r(), 1.7) * 0.9;
        const [x0, y0] = pt(b, R + d0), [x1, y1] = pt(b + (r() - 0.5) * 0.6, R + d1);
        fctx.globalAlpha = 0.25 + r() * 0.45;
        fctx.lineWidth = (0.4 + r() * 0.5) * U;
        fctx.beginPath(); fctx.moveTo(x0, y0); fctx.lineTo(x1, y1); fctx.stroke();
      }
      // a handful of drifting "breath" particles
      for (let i = 0; i < 45 * f.out; i++) {
        const b = f.angle + r.gauss() * sg * 1.2;
        breath.push({ b, d: R + reach * (0.2 + r() * 0.9), s: (0.5 + r() * 0.9) * U, ph: r() * 6.28, sp: 0.25 + r() * 0.5 });
      }
    }
    // background corona from per-subject variance
    if (gain > 0.01) {
      for (const x of m.bg) {
        const r = rngFor(hash(x.id) ^ 31);
        const n = Math.floor(28 * gain * x.v * 4);
        for (let i = 0; i < n; i++) {
          const b = x.angle + r.gauss() * 3.5;
          const d = R * 0.08 * gain * x.v * 4 * Math.pow(r(), 2.4);
          const [px, py] = pt(b, R + d + 1.2 * U);
          fctx.globalAlpha = 0.25 + r() * 0.5;
          fctx.beginPath(); fctx.arc(px, py, (0.25 + r() * 0.35) * U, 0, 6.283); fctx.fill();
        }
      }
    }
    // radial motion-blur streaks (state C)
    if (c > 0.02) {
      const r = rngFor(4242);
      const bx = rx - c * 0.3 * R;
      const ns = Math.floor(170 * c);
      for (let i = 0; i < ns; i++) {
        const ang = Math.PI + r.gauss() * 0.95; // from the black mass, radial about its centre
        const sx = bx + Math.cos(ang) * R * 1.0, sy = cy + Math.sin(ang) * R * 1.0;
        const len = R * (0.12 + 0.55 * Math.pow(r(), 1.6)) * c;
        const ex = sx + Math.cos(ang) * len, ey = sy + Math.sin(ang) * len;
        const gr = fctx.createLinearGradient(sx, sy, ex, ey);
        gr.addColorStop(0, 'rgba(10,10,10,0.55)'); gr.addColorStop(1, 'rgba(10,10,10,0)');
        fctx.globalAlpha = 0.12 + r() * 0.35;
        fctx.strokeStyle = gr;
        fctx.lineWidth = (1 + r() * 5) * U;
        fctx.beginPath(); fctx.moveTo(sx, sy); fctx.lineTo(ex, ey); fctx.stroke();
      }
    }

    // ---- inward bleed (clipped to the pale disc) ----
    if (m.inn > 0.03) {
      const r = rngFor(808);
      const eyeball = smooth(0.35, 0.8, m.inn); // heavier on the left at extreme divergence
      ictx.fillStyle = INK;
      const place = (b, depth, alpha, size) => {
        const [x, y] = pt(b, R - depth);
        ictx.globalAlpha = alpha;
        ictx.beginPath(); ictx.arc(x, y, size, 0, 6.283); ictx.fill();
      };
      for (const f of m.flares) {
        if (f.inn < 0.03) continue;
        const rr = rngFor(hash(f.id) ^ 5);
        const sg = Math.max(3, 3 + f.spread * 1.4);
        const n = Math.floor(1400 * f.inn);
        for (let i = 0; i < n; i++) {
          const dpt = R * 0.5 * f.inn * Math.pow(rr(), 2.2);
          place(f.angle + rr.gauss() * sg, dpt, 0.06 + rr() * 0.25, (0.5 + rr() * 1.4) * U);
        }
      }
      const nl = Math.floor(5200 * eyeball * m.inn);
      for (let i = 0; i < nl; i++) {
        const b = 270 + r.gauss() * 38;
        const dpt = R * 0.55 * m.inn * Math.pow(r(), 1.8);
        place(b, dpt, 0.04 + r() * 0.16, (0.6 + r() * 1.8) * U);
      }
    }

    // ---- compose into cache ----
    if (c > 0.002) {
      // crescent: blurred, then cut with the pale disc (crisp edge, same tone as the field)
      const cut = mk(); cut.width = W; cut.height = H;
      const cc = cut.getContext('2d');
      if (hasFilter) { cc.filter = 'blur(' + (2 * U).toFixed(1) + 'px)'; cc.drawImage(cres, 0, 0); cc.filter = 'none'; }
      else cc.drawImage(cres, 0, 0);
      cc.globalCompositeOperation = 'destination-out';
      cc.fillStyle = '#000';
      cc.beginPath(); cc.arc(rx, cy, R - 0.4 * U, 0, 6.283); cc.fill();
      cctx.drawImage(cut, 0, 0);
    }
    blurDraw(cctx, smoke, 2.2 * U, 0.95);
    blurDraw(cctx, smoke, 0.5 * U, 0.55);
    blurDraw(cctx, fine, 0.45 * U, 1);
    cctx.drawImage(fine, 0, 0);
    if (m.inn > 0.03) {
      cctx.save();
      cctx.beginPath(); cctx.arc(rx, cy, R - 0.3 * U, 0, 6.283); cctx.clip();
      blurDraw(cctx, inner, 5 * U, 1);
      blurDraw(cctx, inner, 2 * U, 0.45);
      cctx.restore();
    }
    // ---- crisp spikes (after the blur) ----
    drawSpikes(cctx, m, c, widthAt);
  }

  function drawSpikes(g, m, c, widthAt) {
    g.fillStyle = INK; g.globalAlpha = 0.95;
    for (const f of m.flares) {
      if (f.out < 0.03) continue;
      const r = rngFor(hash(f.id) ^ 2024);
      const mid = smooth(0.45, 0.6, f.sev) * (1 - smooth(0.68, 0.82, f.sev));
      const hi = smooth(0.68, 0.82, f.sev);
      let nMax = Math.round((7 + 16 * f.out) * (1 - 0.55 * mid) * (1 - 0.15 * hi));
      nMax += Math.round(Math.min(f.spread, 10) * 0.8);
      const n = Math.round(nMax * smooth(0.02, 0.2, f.out));
      const sg = 7 + f.spread * 0.9;
      const lenK = R * (0.1 + 0.42 * f.out) * (1 - 0.35 * mid) * (1 + 0.1 * hi);
      for (let i = 0; i < nMax; i++) {
        const b = f.angle + r.gauss() * sg, L0 = (0.35 + 0.65 * Math.pow(r(), 0.8)), lean = (r() - 0.5) * 0.22;
        const w0 = (1.3 + r() * 1.8) * U, nod = (1.1 + r() * 1.6) * U, k1 = (r() - 0.5) * 0.35, k2 = (r() - 0.5) * 0.35;
        if (i >= n) continue; // stable prefix as amount ramps
        const L = lenK * L0, base = R + widthAt(b) * 0.4;
        const segs = 4;
        let ang = (b - 90) * D2R + lean, [x, y] = pt(b, base);
        const left = [], right = [];
        for (let s = 0; s <= segs; s++) {
          const t = s / segs, w = w0 * (1 - t) * (1 - t * 0.3) / 2;
          const nx = -Math.sin(ang), ny = Math.cos(ang);
          left.push([x + nx * w, y + ny * w]); right.push([x - nx * w, y - ny * w]);
          if (s === 2) ang += k1; if (s === 3) ang += k2;
          x += Math.cos(ang) * L / segs; y += Math.sin(ang) * L / segs;
        }
        g.beginPath();
        left.forEach(([px, py], j) => (j ? g.lineTo(px, py) : g.moveTo(px, py)));
        for (let j = right.length - 1; j >= 0; j--) g.lineTo(right[j][0], right[j][1]);
        g.closePath(); g.fill();
        if (r() < 0.8) { const [nx0, ny0] = pt(b, base - 0.4 * U); g.beginPath(); g.arc(nx0, ny0, nod, 0, 6.283); g.fill(); }
      }
    }
  }

  // ---- labels ----
  function computeLabel() {
    if (!state) return null;
    const divs = state.divergences || [];
    if (focusRid) {
      const mine = divs.filter((d) => d.focal_resident === focusRid || (d.resident_ids || []).includes(focusRid))
        .sort((a, b) => (b.focal_resident === focusRid) - (a.focal_resident === focusRid) || b.severity - a.severity);
      if (mine.length) return { ...labelFromDivergence(mine[0]), key: 'f:' + focusRid + ':' + mine[0].divergence_id, focus: true };
      const p = (state.geo && state.geo.resident_polar && state.geo.resident_polar[focusRid]) || [0, 0];
      const res = (state.residents || []).find((x) => x.resident_id === focusRid);
      return {
        key: 'q:' + focusRid, status: 'ANALYSIS:', place: clean(res ? res.name : focusRid).toUpperCase(),
        small: ['NO DIVERGENCE FLAGGED', 'BEARING ' + p[0].toFixed(1) + '°  RADIUS ' + p[1].toFixed(2)],
        angle: p[0], sev: 0, focus: true, quiet: true,
      };
    }
    if (!divs.length) return null;
    const top = divs.reduce((a, b) => (b.severity > a.severity ? b : a));
    return labelFromDivergence(top);
  }
  function refreshLabel() {
    const n = computeLabel();
    const key = n ? n.key : null;
    if ((label ? label.key : null) === key) return;
    prevLabel = label; label = n; labelT = 0;
    updateFocusRot();
  }
  function labelPos(l) { return l && l.sev >= 0.68 ? 'br' : 'tl'; }
  function updateFocusRot() {
    if (!focusRid || !label) { viewRotTarget = 0; return; }
    const target = labelPos(label) === 'tl' ? 322 : 140;
    viewRotTarget = wrap180(target - label.angle);
  }

  function drawLabel(l, alpha) {
    if (!l || alpha <= 0.01) return;
    const soft = view === 'citizen' ? 0.55 : 1;
    const pos = labelPos(l);
    const m = 0.035 * S;
    const f1 = 12 * U, f2 = 7.8 * U;
    ctx.save();
    ctx.globalAlpha = alpha * soft;
    ctx.fillStyle = INK; ctx.textBaseline = 'alphabetic';
    ctx.font = '700 ' + f1 + 'px ' + SANS;
    const wStatus = ctx.measureText(l.status + ' ').width;
    ctx.font = '400 ' + f1 + 'px ' + SANS;
    const wPlace = ctx.measureText(l.place).width;
    ctx.font = '400 ' + f2 + 'px ' + MONO;
    const wSmall = Math.max(0, ...l.small.map((s) => ctx.measureText(s).width));
    const bw = Math.max(wStatus + wPlace, wSmall);
    const lines = view === 'citizen' ? [] : l.small;
    const bh = f1 + lines.length * f2 * 1.45 + 2 * U;
    const x0 = pos === 'tl' ? m : W - m - bw;
    const y0 = (pos === 'tl' ? m : H - 0.02 * S - bh) + f1;
    ctx.lineJoin = 'round'; ctx.strokeStyle = lerpColor(FIELD, FIELD_C, crescentW); ctx.lineWidth = 3 * U;
    const T = (txt, x, y) => { ctx.strokeText(txt, x, y); ctx.fillText(txt, x, y); };
    ctx.font = '700 ' + f1 + 'px ' + SANS; T(l.status, x0, y0);
    ctx.font = '400 ' + f1 + 'px ' + SANS; T(l.place, x0 + wStatus, y0);
    ctx.font = '400 ' + f2 + 'px ' + MONO; ctx.globalAlpha = alpha * soft * 0.85;
    lines.forEach((s, i) => T(s, x0, y0 + f2 * 1.55 * (i + 1) + 1 * U));
    // hairline leader to the focal point on the ring
    if (view !== 'citizen') {
      const a = (l.angle + viewRot) * D2R;
      const fx = rx + Math.sin(a) * R, fy = cy - Math.cos(a) * R;
      const sx = x0 + 4 * U, sy = pos === 'tl' ? y0 + (lines.length ? f2 * 1.55 * lines.length + 5 * U : 4 * U) : y0 - f1 - 3 * U;
      ctx.globalAlpha = alpha * 0.55; ctx.strokeStyle = INK; ctx.lineWidth = Math.max(0.5, 0.6 * dpr);
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(fx, fy); ctx.stroke();
      ctx.beginPath(); ctx.arc(fx, fy, 1.4 * U, 0, 6.283); ctx.fill();
    }
    ctx.restore();
  }

  // ---- frame ----
  function frame(now) {
    raf = 0;
    if (!running) return;
    raf = requestAnimationFrame(frame);
    if (now - lastFrame < 30) return; // ~30fps cap
    const dt = Math.min(0.1, (now - lastFrame) / 1000 || 0.033);
    lastFrame = now;
    draw(now, dt);
  }

  function draw(now, dt) {
    if (transitioning) {
      const t = clamp((now - tStart) / TRANSITION_MS);
      shown = interpModel(from, to, easeIO(t));
      dirty = true;
      if (t >= 1) { transitioning = false; shown = to; }
    }
    if (dirty) { rebuild(shown); dirty = false; }
    // focus easing
    const dRot = wrap180(viewRotTarget - viewRot);
    viewRot += dRot * (1 - Math.exp(-dt / 0.2));
    if (Math.abs(dRot) < 0.01) viewRot = viewRotTarget;
    if (labelT < 1) labelT = Math.min(1, labelT + dt / 0.35);

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1; ctx.filter = 'none';
    ctx.fillStyle = lerpColor(FIELD, FIELD_C, crescentW);
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    ctx.translate(rx, cy); ctx.rotate(viewRot * D2R); ctx.translate(-rx, -cy);
    ctx.drawImage(cache, 0, 0);
    // the hairline (the plan itself): always there, a line with width zero
    ctx.strokeStyle = INK;
    ctx.globalAlpha = 1;
    ctx.lineWidth = Math.max(0.5, 0.6 * dpr);
    ctx.beginPath(); ctx.arc(rx, cy, R, 0, 6.283); ctx.stroke();
    ctx.restore();

    // slow breathing particles
    if (breath.length) {
      const t = now / 1000;
      ctx.fillStyle = INK;
      for (const p of breath) {
        const b = p.b + viewRot + Math.sin(t * p.sp + p.ph) * 0.35;
        const d = p.d + Math.sin(t * p.sp * 1.3 + p.ph * 2) * 2.2 * U;
        const [x, y] = pt(b, d);
        ctx.globalAlpha = 0.25 + 0.3 * (0.5 + 0.5 * Math.sin(t * p.sp * 2 + p.ph));
        ctx.beginPath(); ctx.arc(x, y, p.s, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }

    if (prevLabel && labelT < 1) drawLabel(prevLabel, 1 - labelT);
    drawLabel(label, labelT);
  }

  function requestDraw() {
    if (!running) return;
    lastFrame = 0;
  }

  function start() {
    if (running) return;
    running = true;
    if (!raf) raf = requestAnimationFrame(frame);
  }
  function stop() { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; }
  const onVis = () => (document.hidden ? stop() : start());
  document.addEventListener('visibilitychange', onVis);

  // ---- interaction ----
  function pick(ev) {
    if (!state || !state.geo || !state.geo.resident_polar) return null;
    const rc = canvasEl.getBoundingClientRect();
    const px = ((ev.clientX - rc.left) / rc.width) * W, py = ((ev.clientY - rc.top) / rc.height) * H;
    const dx = px - rx, dy = py - cy, rho = Math.hypot(dx, dy);
    if (rho < R * 0.6 || rho > R * 1.6) return null;
    const bearing = wrap360(Math.atan2(dx, -dy) / D2R - viewRot);
    let best = null, bd = 1e9;
    for (const [rid, p] of Object.entries(state.geo.resident_polar)) {
      const d = Math.abs(wrap180(p[0] - bearing));
      if (d < bd) { bd = d; best = rid; }
    }
    return bd <= 22 ? best : null;
  }
  canvasEl.addEventListener('click', (ev) => { const rid = pick(ev); if (rid && onSelect) onSelect(rid); });
  canvasEl.addEventListener('pointermove', (ev) => { canvasEl.style.cursor = pick(ev) ? 'pointer' : 'default'; });

  // ---- public API ----
  function resize() {
    const rc = canvasEl.getBoundingClientRect();
    let cw = rc.width, ch = rc.height;
    if (!cw || !ch) { cw = 400; ch = 400; canvasEl.style.width = '400px'; canvasEl.style.height = '400px'; }
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = Math.max(8, Math.round(cw * dpr)); H = Math.max(8, Math.round(ch * dpr));
    for (const c of [canvasEl, cache, smoke, cres, fine, inner]) { c.width = W; c.height = H; }
    S = Math.min(W, H); U = S / 400;
    R = 0.285 * S; cx = W / 2; cy = H / 2; rx = cx;
    dirty = true; requestDraw();
  }
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => resize()).observe(canvasEl);

  function setState(next) {
    const first = !state;
    state = next;
    const model = buildModel(next);
    from = first ? model : shown; to = model;
    if (first) { shown = model; transitioning = false; viewRot = 0; }
    else { tStart = performance.now(); transitioning = true; }
    dirty = true;
    refreshLabel();
    if (first) labelT = 1;
    start(); requestDraw();
  }
  function focus(rid) {
    focusRid = rid || null;
    const n = computeLabel();
    prevLabel = label; label = n; labelT = 0;
    updateFocusRot();
    start();
  }
  function setView(v) { view = v === 'citizen' ? 'citizen' : 'system'; }

  resize();
  start();
  return { setState, focus, setView, resize };
}
