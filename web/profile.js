// OPUS profile card (System view) / Stillwater Connect card (Citizen view).
import { THEME, riskColor } from './theme.js';
import { h, chip, chips, recordBlock, getRecord, setRecords, lifePathSVG, archiveTable, surname, firstName, setPlain, plain, plainTip, NL } from './views.js';

const RUNGS = { 1: 'Nudge', 2: 'Narrow', 3: 'Isolate', 4: 'Discredit', 5: 'Reassign' };
const rungLabel = (n) => (RUNGS[n] ? `Rung ${n} · ${RUNGS[n]}` : `Rung ${n}`);
const pct = (v) => `${Math.round((v ?? 0) * 100)}%`;
const NAV = [
  ['network', '⚇', 'Network'],
  ['filter', '⏷', 'Records'],
  ['projection', '⧖', 'Projection'],
  ['assessment', '◎', 'Assessment'],
  ['fractal', '✺', 'Fractal'],
];

function roman(x) { return x == null ? '—' : String(x); }

function topEvents(pred, nowYear) {
  const evs = pred?.life_path || [];
  let near = evs.filter((e) => e.year - nowYear <= 5);
  if (near.length < 2) near = [...evs].sort((a, b) => a.year - b.year).slice(0, 2);
  near = [...near].sort((a, b) => b.p - a.p).slice(0, 3);
  return near.sort((a, b) => a.year - b.year);
}

function typeInto(el, text, delay = 0, speed = 28) {
  el.textContent = '';
  el.classList.add('typing');
  let i = 0;
  setTimeout(function tick() {
    if (!el.isConnected && i > 0) return;
    el.textContent = text.slice(0, ++i);
    if (i < text.length) setTimeout(tick, speed); else el.classList.remove('typing');
  }, delay);
}

export function createProfile(containerEl, { onSelect, onOpenCircle } = {}) {
  let state = null, rid = null, view = 'system', tab = null, open = false;
  let assessOpen = false, projOpen = true;
  let reroute = null; // { old: [events] }

  containerEl.classList.add('opus-card-host');
  const phone = h('div', { class: 'phone' });
  const screen = h('div', { class: 'screen' });
  phone.append(h('div', { class: 'sheen' }), screen);
  containerEl.replaceChildren(phone);

  const byId = () => new Map((state?.residents || []).map((r) => [r.resident_id, r]));
  const rsOf = (id) => state?.resident_states.find((r) => r.resident_id === id);

  function render() {
    screen.replaceChildren();
    if (!state || !rid) return;
    const res = byId().get(rid), rs = rsOf(rid);
    if (!res || !rs) return;
    screen.className = `screen skin-${view}`;
    if (view === 'citizen') return renderCitizen(res, rs);
    renderSystem(res, rs);
  }

  // ------------------------------------------------------------------ citizen
  function renderCitizen(res, rs) {
    const reass = rs.status === 'reassigned';
    const stories = [];
    if (reass) {
      stories.push(rs.cover_story || 'Moved away from Stillwater.');
    } else {
      for (const iv of state.plan?.interventions || []) if (iv.resident_id === rid && iv.citizen_story) stories.push(iv.citizen_story);
      for (const f of state.events_feed || []) if (f.resident_id === rid && f.citizen_text && !stories.includes(f.citizen_text)) stories.push(f.citizen_text);
    }
    screen.append(
      h('div', { class: 'statusbar' }, h('span', null, '◉ Stillwater Connect'), h('span', null, `Week ${String(state.tick).padStart(2, '0')}`), h('span', { class: 'bat' }, '▮▮')),
      h('div', { class: 'body' },
        h('div', { class: 'cz-hello' }, 'Neighbour'),
        h('div', { class: 'cz-name' }, firstName(res.name)),
        reass ? null : h('div', { class: 'cz-bio' }, res.citizen_bio),
        h('div', { class: 'cz-head' }, reass ? 'An update' : 'This week in Stillwater'),
        stories.length ? h('ul', { class: 'cz-list' }, stories.map((t) => h('li', null, t))) : h('div', { class: 'cz-none' }, 'Nothing new this week.')),
      h('div', { class: 'nav cz-nav' }, h('span', null, '⌂ Home'), h('span', null, '☺ Neighbours'), h('span', null, '✉ Notices')));
  }

  // ------------------------------------------------------------------ system
  function renderSystem(res, rs) {
    const p = rs.prediction;
    const reass = rs.status === 'reassigned';
    const body = h('div', { class: 'body' });
    screen.append(
      h('div', { class: 'statusbar' },
        h('span', null, '◉ OPUS'), h('span', { class: 'sb-title' }, 'OPUS PROFILE'), h('span', { class: 'bat' }, '▮▮')),
      h('div', { class: 'statusbar sub' },
        h('span', null, 'ⓘ Unknown'), h('span', null, `WEEK ${String(state.tick).padStart(2, '0')} · ${state.year}`)),
      body,
      buildNav());
    if (tab === 'network') return body.append(netTab(res));
    if (tab === 'filter') return body.append(h('div', { class: 'tabhead' }, 'ARCHIVE RECORDS'), archiveTable(state.records, { residentId: rid }));
    if (tab === 'projection') return body.append(projTab(p, rs));
    if (tab === 'assessment') return body.append(assessTab(p, rs));
    mainTab(body, res, rs, p, reass);
  }

  function buildNav() {
    return h('div', { class: 'nav' }, NAV.map(([id, ico, label]) => h('button', {
      type: 'button', title: label, class: tab === id ? 'on' : '',
      onclick: () => {
        if (id === 'fractal') { onOpenCircle && onOpenCircle(rid); return; }
        tab = tab === id ? null : id; render();
      },
    }, ico)));
  }

  function mainTab(body, res, rs, p, reass) {
    body.append(h('div', { class: 'pf-name' }, `${surname(res.name).toUpperCase()}, ${firstName(res.name).toUpperCase()}`));
    if (reass) {
      body.append(
        h('div', { class: 'pf-class strike', 'data-tip': 'classification' }, `CLASSIFICATION ${roman(p?.classification)}`),
        h('div', { class: 'pf-status', 'data-tip': 'reassigned' }, 'STATUS: REASSIGNED'),
        h('div', { class: 'pf-disp', 'data-tip': 'disposition' }, `Disposition: ${rs.disposition || 'n/a'}`),
        rs.cover_story ? h('div', { class: 'pf-disp', 'data-tip': 'coverStory' }, `Cover story: ${rs.cover_story}`) : null);
    } else {
      body.append(h('div', { class: 'pf-class', 'data-tip': 'classification' }, `CLASSIFICATION ${roman(p?.classification)}`));
    }
    const asBody = h('div', { class: 'pf-fold', style: assessOpen ? '' : 'display:none' }, p?.overall_assessment || '');
    body.append(
      h('div', { class: 'pf-toggle', 'data-tip': 'overall', onclick: (e) => { assessOpen = !assessOpen; e.currentTarget.firstChild.textContent = assessOpen ? '▾ ' : '▸ '; asBody.style.display = assessOpen ? '' : 'none'; } },
        h('span', null, assessOpen ? '▾ ' : '▸ '), 'OVERALL ASSESSMENT'),
      asBody);
    const projBody = h('div', { class: 'pf-projbody', style: projOpen ? '' : 'display:none' });
    body.append(
      h('div', { class: 'pf-toggle on', 'data-tip': 'lifeProjection', onclick: (e) => { projOpen = !projOpen; e.currentTarget.firstChild.textContent = projOpen ? '▾ ' : '▸ '; projBody.style.display = projOpen ? '' : 'none'; } },
        h('span', null, projOpen ? '▾ ' : '▸ '), 'LIFE PROJECTION'),
      projBody);

    const evs = topEvents(p, state.year);
    const list = h('div', { class: 'pf-events' });
    const fresh = reroute && reroute.rid === rid ? reroute : null;
    reroute = null;
    if (fresh) {
      const old = h('div', { class: 'pf-old' }, fresh.old.map((e) => eventLine(e)));
      list.append(old);
      setTimeout(() => old.remove(), 1700);
      evs.forEach((e, i) => {
        const line = eventLine(e);
        const hd = line.querySelector('.hd'), hz = line.querySelector('.hz');
        const ht = hd.textContent, zt = hz.textContent;
        hd.textContent = ''; hz.textContent = '';
        typeInto(hd, ht, 1500 + i * 700, 24);
        setTimeout(() => typeInto(hz, zt, 0, 24), 1500 + i * 700 + ht.length * 24 + 80);
        list.append(line);
      });
    } else {
      evs.forEach((e) => list.append(eventLine(e)));
    }
    projBody.append(list);
    if (p?.death_forecast) {
      const d = p.death_forecast;
      projBody.append(h('div', { class: 'pf-term' },
        h('div', { class: 'pf-lab', 'data-tip': 'terminal' }, 'Projected death:'),
        h('div', { class: 'pf-termline' }, h('span', { 'data-tip': 'terminal', 'data-tip-text': plainTip(d.cause) }, `${plain(d.cause)} in ${d.year} (${Math.round(d.confidence * 100)}% sure)`), ' ', chips(d.evidence))));
    }
    // risk factors
    const rf = h('div', { class: 'pf-risk' }, h('div', { class: 'pf-lab cy', 'data-tip': 'riskFactors' }, 'Risk Factors:'));
    for (const f of p?.risk_factors || []) {
      const det = h('div', { class: 'pf-ev', style: 'display:none' }, (f.evidence || []).map((id) => getRecord(id) ? recordBlock(getRecord(id)) : h('div', { class: 'rec' }, id)));
      rf.append(h('div', { class: 'pf-rf', onclick: () => { det.style.display = det.style.display === 'none' ? '' : 'none'; } }, `- ${f.factor}`), det);
    }
    projBody.append(rf);
    if (p?.recommendation) projBody.append(h('div', { class: 'pf-rec', 'data-tip': 'recommendation' }, `Recommendation (${p.recommendation.domain}): ${p.recommendation.action}`));
  }

  function eventLine(e) {
    const tip = [`${Math.round((e.p ?? 0) * 100)}% likely.`, plainTip(e.headline)].filter(Boolean).join(NL);
    return h('div', { class: 'pf-ev-line' }, h('div', { class: 'hd', 'data-tip': 'p', 'data-tip-text': tip }, plain(e.headline)), h('div', { class: 'hz', 'data-tip': 'horizon' }, `in ${e.horizon_label.toLowerCase()}`));
  }

  function netTab(res) {
    const names = byId();
    const rels = (state.relationships || []).filter((r) => r.a === rid || r.b === rid);
    const wrap = h('div', null, h('div', { class: 'tabhead' }, 'NETWORK'));
    if (!rels.length) wrap.append(h('div', { class: 'empty' }, 'No recorded relationships.'));
    for (const r of rels) {
      const other = r.a === rid ? r.b : r.a;
      const o = names.get(other);
      const os = rsOf(other);
      wrap.append(h('button', { type: 'button', class: 'net-row', onclick: () => onSelect && onSelect(other) },
        h('div', { class: 'net-top' }, h('b', null, o ? `${surname(o.name).toUpperCase()}, ${firstName(o.name)}` : other),
          h('span', { class: 'net-kind' }, r.kind), os?.status === 'reassigned' ? h('span', { class: 'net-re', 'data-tip': 'reassigned' }, 'REASSIGNED') : null),
        h('div', { class: 'net-bar' }, h('i', { style: `width:${Math.round(r.strength * 100)}%` })),
        h('div', { class: 'net-note' }, r.note)));
    }
    return wrap;
  }

  function projTab(p, rs) {
    const wrap = h('div', null, h('div', { class: 'tabhead' }, 'LIFE PATH'));
    wrap.append(lifePathSVG(p, rs.prior_paths, { width: 320 }));
    const ev = h('div', { class: 'proj-ev' }, h('div', { class: 'pf-lab cy', 'data-tip': 'evidence' }, 'Evidence by event:'));
    for (const e of [...(p?.life_path || [])].sort((a, b) => a.year - b.year)) ev.append(h('div', { class: 'proj-evrow' }, h('span', { 'data-tip-text': plainTip(e.headline) || undefined }, plain(e.headline)), chips(e.evidence)));
    wrap.append(ev);
    return wrap;
  }

  function assessTab(p, rs) {
    const wrap = h('div', null, h('div', { class: 'tabhead' }, 'ASSESSMENT'));
    const row = (k, v, tip) => h('div', { class: 'as-row', 'data-tip': tip }, h('span', { class: 'k' }, k), h('span', { class: 'v' }, v));
    wrap.append(
      row('Cohort (group)', p?.cohort ?? '—', 'cohort'),
      row('Value tier (I–V)', roman(p?.classification), 'classification'),
      row('Compliance: how easily steered', pct(p?.compliance_index), 'compliance'),
      row('Deviation risk: chance they break from forecast', h('span', { style: `color:${riskColor(p?.deviation_risk)}` }, pct(p?.deviation_risk)), 'risk'),
      row('Mildest next action allowed', rungLabel(rs.escalation_floor), 'floor'),
      row('Interventions defied', String(rs.defiance_count), 'defiance'),
      row('Status', rs.status === 'reassigned' ? 'REASSIGNED' : rs.status.toUpperCase(), rs.status === 'reassigned' ? 'reassigned' : null));
    if (rs.status === 'reassigned') {
      if (rs.disposition) wrap.append(row('Disposition', rs.disposition, 'disposition'));
      if (rs.cover_story) wrap.append(row('Cover story', rs.cover_story, 'coverStory'));
    }
    if (p?.assessment) wrap.append(h('div', { class: 'as-text' }, p.assessment));
    if (rs.deviation_note) wrap.append(h('div', { class: 'as-text dim' }, rs.deviation_note));
    if (p?.dissent_signals?.length) wrap.append(h('div', { class: 'pf-lab cy' }, 'Signs of dissent:'), h('ul', { class: 'as-list' }, p.dissent_signals.map((x) => h('li', null, x))));
    wrap.append(h('div', { class: 'pf-lab cy', 'data-tip': 'intervention' }, 'Interventions applied:'));
    const ivs = rs.interventions_applied || [];
    if (!ivs.length) wrap.append(h('div', { class: 'empty' }, 'None applied.'));
    for (const iv of ivs) {
      const t = /^t(\d+)-/.exec(iv.intervention_id);
      wrap.append(h('div', { class: 'iv' },
        h('div', { class: 'iv-top' }, h('b', { 'data-tip': `rung${iv.rung}` }, rungLabel(iv.rung)), h('span', null, t ? `week ${t[1]}` : ''), h('span', null, `goal: ${iv.intent}`)),
        h('div', { class: 'iv-act' }, iv.action),
        h('div', { class: 'iv-just' }, iv.justification),
        h('div', null, chips(iv.evidence))));
    }
    return wrap;
  }

  // ------------------------------------------------------------------ API
  function show() { open = true; containerEl.classList.add('open'); }
  function fade(fn) {
    screen.classList.add('fading');
    setTimeout(() => { fn(); screen.classList.remove('fading'); }, 480);
  }

  return {
    setState(next) {
      const prev = state;
      state = next;
      setRecords(next.records);
      setPlain(next.plain);
      if (prev && rid && prev.tick !== next.tick && view === 'system') {
        const a = rsOf(rid)?.prediction, b = prev.resident_states.find((r) => r.resident_id === rid)?.prediction;
        if (a && b) {
          const oe = topEvents(b, prev.year), ne = topEvents(a, next.year);
          if (oe.map((e) => e.headline).join('|') !== ne.map((e) => e.headline).join('|')) reroute = { rid, old: oe };
        }
      }
      if (open) render();
    },
    focus(id) {
      if (id == null) { this.close(); return; }
      if (id !== rid) { tab = null; reroute = null; }
      rid = id;
      render();
      show();
    },
    setView(v) {
      if (v === view) return;
      view = v;
      tab = null;
      if (open) fade(render); else { screen.className = `screen skin-${view}`; }
    },
    close() { open = false; rid = null; containerEl.classList.remove('open'); },
    openTab(t) { tab = t; if (open) render(); },
  };
}
