// Pure render helpers (DOM/SVG) shared by the card and the drawer.
import { THEME, riskColor } from './theme.js';

const SVGNS = 'http://www.w3.org/2000/svg';

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  fill(el, attrs, kids);
  return el;
}
export function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  fill(el, attrs, kids);
  return el;
}
function fill(el, attrs, kids) {
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') el.setAttribute('class', v);
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
}

// ---- record index + evidence chips -------------------------------------------------------
let RECS = new Map();
export function setRecords(records) {
  RECS = new Map((records || []).map((r) => [r.record_id, r]));
}
export function getRecord(id) { return RECS.get(id); }

let pop = null;
function closePop() { if (pop) { pop.remove(); pop = null; } }
if (typeof document !== 'undefined') {
  document.addEventListener('pointerdown', (e) => {
    if (pop && !pop.contains(e.target) && !e.target.closest?.('.chip')) closePop();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePop(); });
}

export function recordBlock(r) {
  return h('div', { class: 'rec' },
    h('div', { class: 'rec-head' }, h('span', { class: 'rec-id' }, r.record_id), ' ', r.date, ' · ', h('b', null, String(r.kind).toUpperCase())),
    h('div', { class: 'rec-sum' }, r.summary),
    r.detail ? h('div', { class: 'rec-det' }, r.detail) : null);
}

export function chip(id) {
  const c = h('button', { class: 'chip', type: 'button', 'data-tip': 'evidence' }, id);
  c.addEventListener('click', (e) => {
    e.stopPropagation();
    const was = pop && pop.dataset.id === id;
    closePop();
    if (was) return;
    const r = RECS.get(id);
    pop = h('div', { class: 'chip-pop', 'data-id': id },
      r ? recordBlock(r) : h('div', { class: 'rec' }, h('div', { class: 'rec-head' }, id), h('div', { class: 'rec-sum' }, 'Record not in Archive.')));
    document.body.append(pop);
    const b = c.getBoundingClientRect();
    const w = 300;
    pop.style.width = w + 'px';
    pop.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, b.left)) + 'px';
    const ph = pop.offsetHeight;
    pop.style.top = (b.bottom + ph + 8 > window.innerHeight ? Math.max(8, b.top - ph - 6) : b.bottom + 6) + 'px';
  });
  return c;
}
export function chips(ids) {
  return h('span', { class: 'chips' }, (ids || []).map(chip));
}

// ---- life path -------------------------------------------------------------------------
const CLIP = (t, n) => (t.length > n ? t.slice(0, n - 1) + '…' : t);

// plain-English translations of Rehoboam's jargon (state.plain, filled by the backend's plain pass)
export const NL = String.fromCharCode(10);   // newline for tooltip text
let PLAIN = {};
export function setPlain(m) { PLAIN = m || {}; }
export function plain(t) { return (t && PLAIN[t] && PLAIN[t].plain) || t || ''; }
export function plainTip(t) {
  const e = t && PLAIN[t];
  if (!e) return '';
  return e.plain.trim().toLowerCase() === String(t).trim().toLowerCase() ? e.explain : `${e.explain}
Rehoboam's term: "${t}"`;
}

export function lifePathSVG(prediction, priorPaths, { width = 320, height = 0 } = {}) {
  const ev = [...(prediction?.life_path || [])].sort((a, b) => a.year - b.year);
  const ghost = (priorPaths && priorPaths.length ? priorPaths[priorPaths.length - 1] : null) || [];
  const gev = [...ghost].sort((a, b) => a.year - b.year);
  const death = prediction?.death_forecast;
  const slots = ev.length + 1;
  const top = 34, step = 56;
  const H = Math.max(height, top + slots * step + 16);
  const mainX = 78, ghostX = 24, labelX = 100;
  const svg = s('svg', { class: 'lifepath', viewBox: `0 0 ${width} ${H}`, width: '100%', preserveAspectRatio: 'xMinYMin meet' });
  const font = THEME.condensed;

  // legend
  svg.append(
    s('line', { x1: 8, y1: 12, x2: 30, y2: 12, stroke: THEME.cyan, 'stroke-width': 2 }),
    s('text', { x: 36, y: 15, fill: '#9fb3c2', 'font-size': 10, 'font-family': font }, 'CURRENT FORECAST'),
    s('g', { 'data-tip': 'priorPath' },
      s('rect', { x: 126, y: 4, width: 190, height: 16, fill: 'transparent' }),
      s('line', { x1: 130, y1: 12, x2: 152, y2: 12, stroke: '#6b7885', 'stroke-width': 2, 'stroke-dasharray': '3 3' }),
      s('text', { x: 158, y: 15, fill: '#6b7885', 'font-size': 10, 'font-family': font }, 'PRIOR FORECAST (RE-ROUTED)')));

  const yAt = (i) => top + i * step + step / 2 - 8;

  // ghost lane
  if (gev.length) {
    const n = gev.length;
    const gy = (i) => top + 10 + i * ((slots * step - 40) / Math.max(1, n));
    svg.append(s('polyline', { points: gev.map((e, i) => `${ghostX},${gy(i)}`).join(' '), fill: 'none', stroke: '#4b5662', 'stroke-width': 1.5, 'stroke-dasharray': '3 4' }));
    gev.forEach((e, i) => {
      const g = s('g', { opacity: 0.55, 'data-tip': 'priorPath' },
        s('circle', { cx: ghostX, cy: gy(i), r: 3 + e.p * 5, fill: 'none', stroke: '#6b7885', 'stroke-dasharray': '2 2' }));
      svg.append(g);
    });
  }

  // main lane
  const ys = ev.map((_, i) => yAt(i));
  const deathY = yAt(ev.length);
  svg.append(s('polyline', { points: [...ys, deathY].map((y) => `${mainX},${y}`).join(' '), fill: 'none', stroke: THEME.cyan, 'stroke-width': 1.5, opacity: 0.8 }));
  ev.forEach((e, i) => {
    const y = ys[i];
    const r = 5 + (e.p || 0) * 10;
    const g = s('g', { class: 'lp-node', 'data-tip': 'p', 'data-tip-text': [`${Math.round((e.p || 0) * 100)}% likely.`, plainTip(e.headline)].filter(Boolean).join(NL) },
      s('circle', { cx: mainX, cy: y, r, fill: '#0a1018', stroke: THEME.cyan, 'stroke-width': 2 }),
      s('circle', { cx: mainX, cy: y, r: Math.max(1.5, r - 4), fill: THEME.cyan, opacity: 0.25 + 0.6 * (e.p || 0) }),
      s('text', { x: labelX, y: y - 6, fill: THEME.cyan, 'font-size': 14, 'font-weight': 700, 'font-family': font }, CLIP(plain(e.headline), 34)),
      s('text', { x: labelX, y: y + 8, fill: '#9fb3c2', 'font-size': 11, 'font-family': font }, `in ${e.horizon_label.toLowerCase()} · ${e.year} · ${(e.p * 100).toFixed(0)}% likely`),
      s('text', { x: labelX, y: y + 20, fill: '#6b7885', 'font-size': 9.5, 'font-family': font }, (e.evidence || []).join('  ')));
    svg.append(g);
  });
  // death at end, behind a break
  if (death) {
    svg.append(s('g', { 'data-tip': 'terminal', 'data-tip-text': plainTip(death.cause) },
      s('text', { x: mainX, y: (ys[ys.length - 1] + deathY) / 2 + 4, fill: '#6b7885', 'font-size': 12, 'text-anchor': 'middle', 'font-family': font }, '⋮'),
      s('circle', { cx: mainX, cy: deathY, r: 9, fill: '#0a1018', stroke: '#E6EEFF', 'stroke-width': 2 }),
      s('text', { x: mainX, y: deathY + 4, fill: '#E6EEFF', 'font-size': 11, 'text-anchor': 'middle', 'font-family': font }, '†'),
      s('text', { x: labelX, y: deathY - 4, fill: '#E6EEFF', 'font-size': 14, 'font-weight': 700, 'font-family': font }, CLIP(plain(death.cause), 34)),
      s('text', { x: labelX, y: deathY + 10, fill: '#9fb3c2', 'font-size': 11, 'font-family': font },
        `${death.year} · age ${death.age_at_death} · ${(death.confidence * 100).toFixed(0)}% sure`),
      s('text', { x: labelX, y: deathY + 22, fill: '#6b7885', 'font-size': 9.5, 'font-family': font }, (death.evidence || []).join('  '))));
  }
  return svg;
}

// ---- archive table -----------------------------------------------------------------------
export function archiveTable(records, { residentId = null, highlight = [], names = null } = {}) {
  const hl = new Set(highlight || []);
  const rows = (records || []).filter((r) => !residentId || r.resident_id === residentId);
  const showWho = !residentId;
  const head = h('tr', null, ['ID', showWho ? 'SUBJECT' : null, 'DATE', 'KIND', 'SUMMARY', 'DETAIL'].filter(Boolean).map((t) => h('th', t === 'ID' ? { 'data-tip': 'evidence' } : null, t)));
  const body = rows.map((r) => h('tr', { class: hl.has(r.record_id) ? 'hl' : '' },
    h('td', null, chip(r.record_id)),
    showWho ? h('td', null, names?.[r.resident_id] || r.resident_id) : null,
    h('td', { class: 'nw' }, r.date),
    h('td', { class: 'nw' }, r.kind),
    h('td', null, r.summary),
    h('td', { class: 'dim' }, r.detail || '')));
  return h('div', { class: 'archive-wrap' },
    h('table', { class: 'archive' }, h('thead', null, head), h('tbody', null, body)),
    rows.length ? null : h('div', { class: 'empty' }, 'No records.'));
}

// ---- cohort x district heatmap -------------------------------------------------------------
export function cohortHeatmap(state, { onCohort, active = null } = {}) {
  const districts = state.city.districts;
  const cohorts = Object.keys(state.cohort_dissent || {});
  const cell = new Map();
  for (const rs of state.resident_states) {
    const c = rs.prediction?.cohort;
    const d = rs.current_district || state.residents.find((r) => r.resident_id === rs.resident_id)?.home_district;
    if (!c || !d) continue;
    const k = c + '|' + d;
    if (!cell.has(k)) cell.set(k, []);
    cell.get(k).push(rs);
  }
  const shade = (v) => {
    const c = riskColor(v);
    return c;
  };
  const head = h('tr', null, h('th', { 'data-tip': 'cohort' }, 'COHORT'), districts.map((d) => h('th', { 'data-tip': 'districtDissent' }, d.name)), h('th', { 'data-tip': 'cohortDissent' }, 'COHORT AVG'));
  const rows = cohorts.map((c) => h('tr', { class: active === c ? 'act' : '' },
    h('th', { class: 'rowh', onclick: () => onCohort && onCohort(c) }, c),
    districts.map((d) => {
      const list = cell.get(c + '|' + d.district_id);
      if (!list) return h('td', { class: 'hm-empty' }, '·');
      const v = list.reduce((a, r) => a + (r.prediction?.deviation_risk ?? 0), 0) / list.length;
      return h('td', { class: 'hm-cell', style: `background:${shade(v)};color:#0B0D10`, 'data-tip-title': `${c} / ${d.name}`, 'data-tip-text': `${list.length} subject(s). Average chance of deviating from forecast: ${Math.round(v * 100)}%.` }, v.toFixed(2));
    }),
    h('td', { class: 'hm-all', 'data-tip': 'cohortDissent', style: `color:${riskColor(state.cohort_dissent[c])}` }, (state.cohort_dissent[c] ?? 0).toFixed(2))));
  const foot = h('tr', { class: 'foot' }, h('th', { 'data-tip': 'districtDissent' }, 'DISTRICT DISSENT'),
    districts.map((d) => h('td', { style: `color:${riskColor(state.district_dissent?.[d.district_id])}` }, (state.district_dissent?.[d.district_id] ?? 0).toFixed(2))), h('td'));
  return h('div', { class: 'heatmap-wrap' },
    h('table', { class: 'heatmap' }, h('thead', null, head), h('tbody', null, rows, foot)),
    h('div', { class: 'hm-note' }, 'Each cell: average deviation risk of that cohort in that district (redder = more likely to break from forecast). Click a cohort name to highlight its members in the city.'));
}

// ---- gallery -----------------------------------------------------------------------------
export function surname(name) { const p = name.trim().split(/\s+/); return p[p.length - 1]; }
export function firstName(name) { return name.trim().split(/\s+/)[0]; }

export function gallery(state, { view = 'system', onSelect, selected = null } = {}) {
  const byId = new Map(state.residents.map((r) => [r.resident_id, r]));
  const cards = state.resident_states.map((rs) => {
    const res = byId.get(rs.resident_id);
    const p = rs.prediction;
    const reass = rs.status === 'reassigned';
    const card = h('button', { type: 'button', class: `mini${reass ? ' reassigned' : ''}${selected === rs.resident_id ? ' sel' : ''}`, onclick: () => onSelect && onSelect(rs.resident_id) });
    if (view === 'citizen') {
      card.append(
        h('div', { class: 'mini-name cz' }, firstName(res.name)),
        h('div', { class: 'mini-sub' }, reass ? (rs.cover_story || '') : res.citizen_bio));
    } else {
      const top = [...(p?.life_path || [])].sort((a, b) => a.year - b.year)[0];
      card.append(
        h('div', { class: 'mini-name' }, `${surname(res.name).toUpperCase()}, ${firstName(res.name).toUpperCase()}`),
        h('div', { class: 'mini-class' + (reass ? ' strike' : ''), 'data-tip': 'classification' }, `CLASSIFICATION ${p?.classification ?? '—'}`),
        h('div', { class: 'mini-risk', 'data-tip': 'risk' }, h('i', { style: `width:${Math.round((p?.deviation_risk ?? 0) * 100)}%;background:${riskColor(p?.deviation_risk)}` })),
        h('div', { class: 'mini-sub' }, top ? plain(top.headline) : ''));
    }
    if (reass) card.append(h('div', { class: 'stamp', 'data-tip': 'reassigned' }, 'REASSIGNED'));
    return card;
  });
  return h('div', { class: 'gallery' }, cards);
}
