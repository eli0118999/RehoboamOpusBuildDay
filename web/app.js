// Shell: state loading, header, tick scrubber, view toggle, linked selection, feed, drawer, final screen.
import { THEME } from './theme.js';
import { createProfile } from './profile.js';
import { installTooltips } from './tooltip.js';
import { FEED_TIP } from './glossary.js';
import { setRecords, setPlain, cohortHeatmap, gallery, archiveTable, surname, firstName } from './views.js';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);

const app = {
  ticks: [], latest: 0, live: false, runId: params.get('run') || null,
  cache: new Map(), state: null, tickIdx: 0,
  view: 'system', selected: null, drawerTab: 'heatmap', cohort: null,
  world: null, circle: null, profile: null,
};
window.app = app;

// ---------------------------------------------------------------- data
async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(url + ' ' + r.status);
  const ct = r.headers.get('content-type') || '';
  if (!ct.includes('json')) throw new Error('not json: ' + url);
  return r.json();
}
const q = () => (app.runId ? `run=${encodeURIComponent(app.runId)}&` : '');

async function loadTicks() {
  try {
    const t = await getJSON('/api/ticks' + (app.runId ? `?run=${encodeURIComponent(app.runId)}` : ''));
    app.live = true; app.runId = t.run_id; app.ticks = t.ticks; app.latest = t.latest ?? Math.max(...t.ticks);
  } catch {
    app.live = false;
    if (!app.fixture) {
      app.fixture = await (await fetch('fixtures/sample_state.json')).json();
      for (const s of app.fixture.ticks) app.cache.set(s.tick, s);
    }
    app.ticks = app.fixture.ticks.map((s) => s.tick);
    app.latest = Math.max(...app.ticks);
  }
  $('live-controls').hidden = !app.live;
  const led = $('led'); if (led) { led.classList.toggle('live', app.live); led.classList.toggle('replay', !app.live); }
}

async function getState(n) {
  if (app.cache.has(n) && !app.live) return app.cache.get(n);
  if (app.live) {
    const st = await getJSON(`/api/state?${q()}tick=${n}`);
    app.cache.set(n, st);
    return st;
  }
  return app.cache.get(n);
}

// ---------------------------------------------------------------- safe module calls
function safe(label, fn) {
  try { return fn(); } catch (e) { console.error(`[${label}]`, e); }
}

async function loadModules() {
  const skip = (params.get('skip') || '').split(',');  // debug: ?skip=world,circle
  try {
    if (skip.includes('world')) throw new Error('skipped');
    const m = await import('./world.js');
    app.world = m.createWorld($('stage'), { onSelect: (rid) => select(rid) });
  } catch (e) { console.error('[world] unavailable', e); $('stage-note').hidden = false; }
  try {
    if (skip.includes('circle')) throw new Error('skipped');
    const m = await import('./circle.js');
    app.circle = m.createCircle($('circle'), { onSelect: (rid) => select(rid) });
  } catch (e) { console.error('[circle] unavailable', e); }
  app.profile = createProfile($('card'), { onSelect: (rid) => select(rid), onOpenCircle: () => focusCircle() });
}

// ---------------------------------------------------------------- render
const pad = (n) => String(n).padStart(2, '0');

function renderHeader() {
  const s = app.state, m = s.metrics;
  $('m-stab').querySelector('.v').textContent = `${m.stability.toFixed(1)}%`;
  $('m-loop').querySelector('.v').textContent = `${m.active}/${m.total}`;
  $('m-acc').querySelector('.v').textContent = m.accuracy == null ? '--' : m.accuracy.toFixed(2);
  $('tick-n').textContent = pad(s.tick);
  $('tick-prev').disabled = app.tickIdx <= 0;
  $('tick-next').disabled = app.tickIdx >= app.ticks.length - 1;
  for (const b of document.querySelectorAll('#view-toggle button')) b.classList.toggle('on', b.dataset.view === app.view);
}

const KIND_CLASS = { defiance: 'k-defiance', reassignment: 'k-reassign', disruption: 'k-disruption' };

function renderFeed() {
  const feed = $('feed');
  feed.replaceChildren();
  const evs = [...(app.state.events_feed || [])].reverse();
  const head = document.createElement('div');
  head.className = 'feed-head';
  head.dataset.tip = 'feed';
  head.textContent = app.view === 'system' ? `EVENT STREAM · WEEK ${pad(app.state.tick)}` : `STILLWATER CONNECT · WEEK ${pad(app.state.tick)}`;
  feed.append(head);
  const list = document.createElement('div');
  list.className = 'feed-list';
  for (const e of evs) {
    const row = document.createElement('div');
    row.className = `fl ${KIND_CLASS[e.kind] || ''}`;
    row.dataset.rid = e.resident_id || '';
    if (e.resident_id) row.addEventListener('click', () => select(e.resident_id));
    if (app.view === 'system') {
      const tag = document.createElement('span');
      tag.className = 'tag'; tag.textContent = e.kind.toUpperCase();
      tag.dataset.tip = FEED_TIP[e.kind] || e.kind;
      const tx = document.createElement('span');
      tx.className = 'tx'; tx.textContent = (e.system_text || '').toUpperCase();
      row.append(tag, tx);
    } else {
      const tx = document.createElement('span');
      tx.className = 'tx'; tx.textContent = e.citizen_text || '';
      row.append(tx);
    }
    list.append(row);
  }
  if (!evs.length) list.innerHTML = '<div class="fl dim">No events this week.</div>';
  feed.append(list);
  highlightFeed();
}

function highlightFeed() {
  for (const r of document.querySelectorAll('#feed .fl')) r.classList.toggle('hl', !!app.selected && r.dataset.rid === app.selected);
  const first = document.querySelector('#feed .fl.hl');
  if (first) first.scrollIntoView({ block: 'nearest' });
}

function renderDrawer() {
  const body = $('drawer-body');
  for (const b of document.querySelectorAll('#drawer .drawer-tabs [data-tab]')) b.classList.toggle('on', b.dataset.tab === app.drawerTab);
  if (!app.state) return;
  body.replaceChildren();
  const s = app.state;
  if (app.view === 'citizen' && app.drawerTab !== 'gallery') {
    body.innerHTML = '<div class="empty">SYSTEM VIEW ONLY</div>';
    return;
  }
  if (app.drawerTab === 'heatmap') body.append(cohortHeatmap(s, { active: app.cohort, onCohort: (c) => highlightCohort(app.cohort === c ? null : c) }));
  else if (app.drawerTab === 'gallery') body.append(gallery(s, { view: app.view, selected: app.selected, onSelect: (rid) => select(rid) }));
  else body.append(archiveTable(s.records, { highlight: [], names: Object.fromEntries(s.residents.map((r) => [r.resident_id, `${surname(r.name)}, ${firstName(r.name)}`])) }));
}

function highlightCohort(c) {
  app.cohort = c;
  safe('world.highlightCohort', () => app.world?.highlightCohort(c));
  renderDrawer();
}

async function goTo(n, { animate = true } = {}) {
  const idx = app.ticks.indexOf(n);
  if (idx < 0) return;
  const st = await getState(n);
  if (!st) return;
  app.tickIdx = idx;
  app.state = st;
  setRecords(st.records);
  setPlain(st.plain);
  renderHeader();
  renderFeed();
  renderDrawer();
  safe('world.setState', () => app.world?.setState(st, { animate }));
  safe('circle.setState', () => app.circle?.setState(st));
  safe('profile.setState', () => app.profile?.setState(st));
  if (app.selected && !st.resident_states.some((r) => r.resident_id === app.selected)) select(null);
}

// ---------------------------------------------------------------- selection / view
function select(rid) {
  app.selected = rid || null;
  safe('world.focus', () => app.world?.focus(app.selected));
  safe('circle.focus', () => app.circle?.focus(app.selected));
  safe('profile.focus', () => app.selected ? app.profile?.focus(app.selected) : app.profile?.close());
  if (!app.selected) $('circle-panel').classList.remove('big'), requestAnimationFrame(() => safe('circle.resize', () => app.circle?.resize()));
  highlightFeed();
  if ($('drawer').classList.contains('open') && app.drawerTab === 'gallery') renderDrawer();
}
app.select = select;

function setView(v) {
  app.view = v;
  document.body.classList.remove('view-citizen', 'view-system');
  document.body.classList.add('view-' + v);
  safe('world.setView', () => app.world?.setView(v));
  safe('circle.setView', () => app.circle?.setView(v));
  safe('profile.setView', () => app.profile?.setView(v));
  if (app.state) { renderHeader(); renderFeed(); renderDrawer(); }
}
app.setView = setView;

function focusCircle() {
  const p = $('circle-panel');
  p.classList.toggle('big');
  setTimeout(() => safe('circle.resize', () => app.circle?.resize()), 360);
  setTimeout(() => safe('circle.resize', () => app.circle?.resize()), 800);
}

function setDrawer(open, tab) {
  if (tab) app.drawerTab = tab;
  $('drawer').classList.toggle('open', open);
  $('btn-drawer').textContent = open ? 'DRAWER ▾' : 'DRAWER ▴';
  $('btn-drawer').classList.toggle('on', open);
  renderDrawer();
}

app.showFinal = function showFinal(on = true) {
  const f = $('final');
  if (on && app.state) {
    const m = app.state.metrics;
    f.querySelector('.final-text').innerHTML = '';
    const l1 = document.createElement('div');
    l1.textContent = `Stability: ${m.stability.toFixed(1)}%.`;
    const l2 = document.createElement('div');
    l2.textContent = `Active loop: ${m.active} of ${m.total}.`;
    f.querySelector('.final-text').append(l1, l2);
    select(null);  // still city, no selection; the circle takes the centre (real state: hairline only at zero divergence)
  }
  f.classList.toggle('show', !!on);
  document.body.classList.toggle('final-mode', !!on);
  setTimeout(() => safe('circle', () => app.circle?.resize()), 50);
  setTimeout(() => safe('circle', () => app.circle?.resize()), 1300);
};

// ---------------------------------------------------------------- actions
function toast(msg, ms = 3500) {
  const t = $('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), ms);
}

async function post(path) {
  const r = await fetch(path, { method: 'POST' });
  let body = null;
  try { body = await r.json(); } catch { /* ignore */ }
  if (!r.ok) throw new Error(body?.error || r.status);
  return body;
}

async function doTick() {
  const b = $('btn-tick');
  b.disabled = true; b.textContent = 'RUNNING…';
  try {
    await post(`/api/tick${app.runId ? `?run=${encodeURIComponent(app.runId)}` : ''}`);
    app.cache.clear();
    await loadTicks();
    await goTo(app.latest);
  } catch (e) { toast('NEXT WEEK FAILED: ' + e.message); }
  b.disabled = false; b.textContent = 'NEXT WEEK ▸';
}

const DISRUPT_TITLES = { factory_closure: 'Factory closure', organiser_arrives: 'Organiser arrives', heatwave: 'Heatwave', data_leak: 'Data leak' };

async function doDisrupt(id) {
  $('disrupt-menu').hidden = true;
  try {
    const r = await post(`/api/disrupt/${id}${app.runId ? `?run=${encodeURIComponent(app.runId)}` : ''}`);
    toast(`DISRUPTION QUEUED: ${DISRUPT_TITLES[r.queued || id] || (r.queued || id)}`);
  } catch (e) { toast('DISRUPT FAILED: ' + e.message); }
}

function wire() {
  $('tick-prev').onclick = () => goTo(app.ticks[app.tickIdx - 1]);
  $('tick-next').onclick = () => goTo(app.ticks[app.tickIdx + 1]);
  for (const b of document.querySelectorAll('#view-toggle button')) b.onclick = () => setView(b.dataset.view);
  $('btn-drawer').onclick = () => setDrawer(!$('drawer').classList.contains('open'));
  $('drawer-close').onclick = () => setDrawer(false);
  for (const b of document.querySelectorAll('#drawer [data-tab]')) b.onclick = () => setDrawer(true, b.dataset.tab);
  $('btn-tick').onclick = doTick;
  $('btn-disrupt').onclick = () => { $('disrupt-menu').hidden = !$('disrupt-menu').hidden; };
  for (const b of document.querySelectorAll('#disrupt-menu [data-id]')) b.onclick = () => doDisrupt(b.dataset.id);
  $('circle-zoom').onclick = focusCircle;
  $('legend-toggle').onclick = () => { const l = $('legend'); const o = l.classList.toggle('open'); $('legend-caret').innerHTML = o ? '&#9662;' : '&#9656;'; };
  window.addEventListener('resize', () => { safe('world.resize', () => app.world?.resize()); safe('circle.resize', () => app.circle?.resize()); });
  window.addEventListener('keydown', (e) => {
    if (e.target.matches?.('input,textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (k === 'ArrowLeft') { if (app.tickIdx > 0) goTo(app.ticks[app.tickIdx - 1]); }
    else if (k === 'ArrowRight') { if (app.tickIdx < app.ticks.length - 1) goTo(app.ticks[app.tickIdx + 1]); }
    else if (k === 'c' || k === 'C') setView('citizen');
    else if (k === 's' || k === 'S') setView('system');
    else if (k === 'f' || k === 'F') app.showFinal(!$('final').classList.contains('show'));
    else if (k === 'd' || k === 'D') setDrawer(!$('drawer').classList.contains('open'));
    else if (k === 'Escape') { app.showFinal(false); select(null); }
  });
}

// ---------------------------------------------------------------- boot
async function boot() {
  installTooltips();
  wire();
  if (params.get('select') || params.get('drawer') || params.get('final')) { document.body.classList.add('noanim'); setTimeout(() => document.body.classList.remove('noanim'), 2500); }
  await loadTicks();
  await loadModules();
  const v = params.get('view');
  document.body.classList.add('view-system');
  if (v === 'citizen' || v === 'system') setView(v); else setView('system');
  const t = params.has('tick') ? Number(params.get('tick')) : app.latest;
  await goTo(app.ticks.includes(t) ? t : app.latest, { animate: false });
  if (params.get('drawer')) setDrawer(true, params.get('drawer') === '1' ? 'heatmap' : params.get('drawer'));
  if (params.get('select')) {
    select(params.get('select'));
    if (params.get('tab')) app.profile?.openTab(params.get('tab'));
  }
  if (params.get('circle')) focusCircle();
  if (params.get('final')) app.showFinal(true);
}
boot().catch((e) => { console.error('[boot]', e); toast('BOOT FAILED: ' + e.message, 20000); });
