// world.js — Mini Rehoboam 3D "white architectural model" of Stillwater.
// Vanilla ES module + Three.js (import map: "three", "three/addons/"). No textures, no bloom, no CDNs.
// Contract: docs/CONTRACT.md §2 (geography), §5 (API), §6 (display rules).
//
//   createWorld(containerEl, { onSelect }) -> { setState, focus, setView, highlightCohort, resize }
//
// Reads only: state.seed, city, geo, resident_states (+ .prediction), plan.interventions, district_dissent.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

// ---------------------------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------------------------
const COL = {
  bg: '#0B0D10', plinth: '#D9D9D6', building: '#F2F2EE', cyan: '#6FE7FF', amber: '#FFB347', red: '#FF4D4D',
  white: '#F4F4F0',
};
const MONO = '"JetBrains Mono","IBM Plex Mono",Consolas,monospace';

const R = 52;            // plinth radius in world units (geo radius 1.0)
const GRID = 9;          // 9 x 9 block grid
const PITCH = 11;        // block pitch; streets are the gaps
const BLOCK = 7.6;       // block footprint
const PAD_H = 0.16;      // block pad height
const STREET_C = PITCH / 2;

const DOT_R = 0.55, DOT_Y = 1.25;               // subjects are hovering beacon dots
const DOT_TOP = DOT_Y + DOT_R + 0.35;
const DOT_PX = 0.026, HALO_PX = 0.075;           // screen-relative sprite sizes (sizeAttenuation off)
function dotTexture(kind) {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  if (kind === 'halo') {
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,0.9)'); gr.addColorStop(0.35, 'rgba(255,255,255,0.35)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  } else {
    g.fillStyle = 'rgba(11,13,16,0.9)'; g.beginPath(); g.arc(32, 32, 30, 0, Math.PI * 2); g.fill();   // dark rim: reads on the white model
    g.fillStyle = '#ffffff'; g.beginPath(); g.arc(32, 32, 22, 0, Math.PI * 2); g.fill();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
let _dotTex = null, _haloTex = null;
function dotTex() { return _dotTex || (_dotTex = dotTexture('dot')); }
function haloTex() { return _haloTex || (_haloTex = dotTexture('halo')); }
const THREAD_SAMPLES = 48;

const VIEW = {
  citizen: { key: '#FFC89A', keyI: 6.6, az: 238, el: 17, sky: '#FFE2C8', ground: '#7a6258', hemiI: 1.5, fog: '#160f0d', fogD: 0.0014, bg: '#160f0d' },
  system:  { key: '#E6EEFF', keyI: 3.5, az: 128, el: 56, sky: '#DCE3EF', ground: '#767d88', hemiI: 1.0, fog: '#07090c', fogD: 0.0019, bg: '#0B0D10' },
};

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const easeIO = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const DEG = Math.PI / 180;

// seeded rng -------------------------------------------------------------------------------------
function hashStr(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// polar (contract §2) -----------------------------------------------------------------------------
function polarToXZ(b, r) { const a = b * DEG; return { x: Math.sin(a) * r * R, z: -Math.cos(a) * r * R }; }
function normDeg(d) { return ((d % 360) + 360) % 360; }
function inArc(b, arc) {
  const s = normDeg(arc[0]), e = normDeg(arc[1]); b = normDeg(b);
  return s <= e ? (b >= s && b < e) : (b >= s || b < e);
}
function arcDist(b, arc) {
  const s = normDeg(arc[0]); let span = normDeg(arc[1] - arc[0]); if (span === 0) span = 360;
  const mid = s + span / 2; let d = Math.abs(normDeg(b - mid)); if (d > 180) d = 360 - d; return d;
}

// risk colour: white -> amber -> red -----------------------------------------------------------------
const _cW = new THREE.Color(COL.white), _cA = new THREE.Color(COL.amber), _cR = new THREE.Color(COL.red);
function riskColor(v, out = new THREE.Color()) {
  v = clamp(v, 0, 1);
  if (v < 0.5) return out.copy(_cW).lerp(_cA, v / 0.5);
  return out.copy(_cA).lerp(_cR, (v - 0.5) / 0.5);
}

// geometry merge helper (no addons needed) -----------------------------------------------------------
function mergeParts(parts) {
  const pos = [], nor = [];
  for (const g0 of parts) {
    const g = g0.index ? g0.toNonIndexed() : g0;
    pos.push(...g.attributes.position.array);
    nor.push(...g.attributes.normal.array);
    if (g !== g0) g.dispose();
    g0.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.computeBoundingSphere(); out.computeBoundingBox();
  return out;
}
const bx = (w, h, d, x = 0, y = 0, z = 0) => new THREE.BoxGeometry(w, h, d).translate(x, y + h / 2, z);
const cy = (r, h, x = 0, y = 0, z = 0, seg = 18, rt = r) => new THREE.CylinderGeometry(rt, r, h, seg).translate(x, y + h / 2, z);

// ---------------------------------------------------------------------------------------------
// Landmark silhouettes (each returns { geo, top }). Local frame: footprint within +-3.8, front = +z.
// ---------------------------------------------------------------------------------------------
function buildLandmarkGeometry(kind, rng) {
  const P = [];
  let top = 4;
  switch (kind) {
    case 'council': {
      P.push(bx(7.2, 0.35, 7.2, 0, 0, 0), bx(5.2, 0.35, 5.2, 0, 0.35, 0));
      P.push(bx(2.3, 30, 2.3, 0, 0.7, 0));
      P.push(bx(1.5, 6, 1.5, 0, 30.7, 0));
      P.push(cy(0.55, 0.8, 0, 36.7, 0, 14));
      top = 37.5; break;
    }
    case 'employer': { // sawtooth factory
      const W = 7.2, n = 4, tw = W / n, h0 = 2.6, th = 1.7, D = 5.4;
      const s = new THREE.Shape(); s.moveTo(0, 0); s.lineTo(W, 0); s.lineTo(W, h0);
      for (let i = n - 1; i >= 0; i--) { const x0 = i * tw; s.lineTo(x0, h0 + th); s.lineTo(x0, h0); }
      s.lineTo(0, 0);
      P.push(new THREE.ExtrudeGeometry(s, { depth: D, bevelEnabled: false }).translate(-W / 2, 0, -D / 2 - 0.4));
      P.push(cy(0.5, 9.5, 2.9, 0, -3.0, 14, 0.42));
      P.push(bx(2.4, 2.2, 1.6, -2.2, 0, 2.5));
      top = 9.5; break;
    }
    case 'library': { // colonnade
      P.push(bx(7.2, 0.55, 5.4, 0, 0, 0.2));
      P.push(bx(6.0, 3.5, 3.2, 0, 0.55, -0.9));
      for (let i = 0; i < 8; i++) P.push(cy(0.2, 3.5, -3.0 + i * (6.0 / 7), 0.55, 1.45, 10));
      P.push(bx(6.8, 0.4, 1.9, 0, 4.05, 1.05));
      P.push(cy(1.5, 0.9, 0, 4.05, -0.9, 20));
      top = 5.0; break;
    }
    case 'housing_block': {
      P.push(bx(7.4, 1.2, 4.6, 0, 0, 0));
      P.push(bx(7.0, 15.5, 2.5, 0, 1.2, -0.3));
      P.push(bx(1.6, 1.2, 1.6, 2.4, 16.7, -0.3));
      top = 17.9; break;
    }
    case 'school': {
      P.push(bx(7.2, 2.6, 2.3, 0, 0, -1.3));
      P.push(bx(2.4, 2.6, 5.4, -2.4, 0, 0.7));
      P.push(bx(2.0, 1.8, 1.8, 2.3, 0, 1.6));
      P.push(cy(0.07, 5.5, 3.2, 0, 3.0, 6));
      top = 5.5; break;
    }
    case 'shelter': {
      P.push(bx(7.2, 3.4, 2.2, 0, 0, -2.4));
      P.push(bx(2.2, 3.4, 5.4, -2.5, 0, 0));
      P.push(bx(2.2, 3.4, 5.4, 2.5, 0, 0));
      P.push(bx(1.6, 1.0, 1.4, 0, 0, 0.8));
      top = 3.4; break;
    }
    case 'clinic': {
      P.push(bx(7.2, 3.0, 2.4, 0, 0, 0));
      P.push(bx(2.4, 3.0, 7.2, 0, 0, 0));
      P.push(bx(1.8, 1.2, 1.8, 0, 3.0, 0));
      top = 4.2; break;
    }
    case 'police': {
      P.push(bx(6.4, 0.5, 6.4, 0, 0, 0));
      P.push(bx(5.4, 4.2, 5.4, 0, 0.5, 0));
      P.push(bx(2.2, 2.0, 2.2, 1.4, 4.7, 1.0));
      P.push(cy(0.11, 7.0, -1.8, 4.7, -1.8, 8));
      top = 11.7; break;
    }
    case 'court': {
      P.push(bx(7.4, 0.35, 6.4, 0, 0, 0), bx(6.8, 0.35, 5.8, 0, 0.35, 0));
      P.push(bx(5.8, 3.6, 3.2, 0, 0.7, -1.2));
      for (let i = 0; i < 6; i++) P.push(cy(0.26, 3.6, -2.75 + i * 1.1, 0.7, 1.9, 12));
      P.push(bx(6.2, 0.3, 2.0, 0, 4.3, 1.7));
      const tri = new THREE.Shape(); tri.moveTo(-3.1, 0); tri.lineTo(3.1, 0); tri.lineTo(0, 1.1); tri.lineTo(-3.1, 0);
      P.push(new THREE.ExtrudeGeometry(tri, { depth: 0.5, bevelEnabled: false }).translate(0, 4.6, 1.45));
      P.push(bx(6.2, 0.4, 3.2, 0, 4.3, -1.2));
      top = 5.7; break;
    }
    case 'market': {
      P.push(bx(7.4, 2.5, 4.4, 0, 0, -0.9));
      P.push(bx(5.2, 1.0, 3.2, 0, 2.5, -0.9));
      for (let i = 0; i < 5; i++) P.push(bx(1.0, 0.9, 0.9, -3.0 + i * 1.5, 0, 2.3));
      top = 3.5; break;
    }
    case 'transit': {
      P.push(bx(7.4, 0.3, 3.4, 0, 0, 0));
      P.push(bx(7.6, 0.25, 2.6, 0, 3.1, 0));
      for (const x of [-3.2, -1.1, 1.1, 3.2]) P.push(cy(0.12, 2.8, x, 0.3, -0.8, 8), cy(0.12, 2.8, x, 0.3, 0.8, 8));
      P.push(cy(0.9, 1.7, -2.6, 0, -2.6, 16));
      top = 3.4; break;
    }
    case 'park': {
      P.push(cy(3.7, 0.35, 0, 0, 0, 40));
      P.push(cy(1.1, 1.4, 0, 0.35, 0, 18, 0.9));
      P.push(cy(1.7, 0.2, 0, 1.75, 0, 18));
      for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2 + 0.6; P.push(bx(1.0, 0.35, 0.3, Math.sin(a) * 2.7, 0.35, Math.cos(a) * 2.7)); }
      top = 2.0; break;
    }
    case 'underpass': { // bridge deck + abutments (placed across the river)
      P.push(bx(3.6, 0.5, 13.0, 0, -0.4, 0));                      // flush deck (top at +0.1)
      P.push(bx(0.18, 0.5, 13.0, 1.7, 0.1, 0), bx(0.18, 0.5, 13.0, -1.7, 0.1, 0));   // parapets
      P.push(bx(3.2, 1.3, 0.5, 0, -1.7, 6.0), bx(3.2, 1.3, 0.5, 0, -1.7, -6.0));   // abutments under the deck ends
      top = 0.8; break;
    }
    default: {
      P.push(bx(5.4, 3 + rng() * 3, 5.4, 0, 0, 0)); top = 6;
    }
  }
  return { geo: mergeParts(P), top };
}

// ---------------------------------------------------------------------------------------------
// createWorld
// ---------------------------------------------------------------------------------------------
export function createWorld(containerEl, { onSelect } = {}) {
  if (getComputedStyle(containerEl).position === 'static') containerEl.style.position = 'relative';
  injectCSS();

  // ---- renderer / scene / camera ------------------------------------------------------------
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  } catch (e) {
    const msg = document.createElement('div');
    msg.style.cssText = `position:absolute;inset:0;display:grid;place-items:center;color:#889;font:12px ${MONO}`;
    msg.textContent = 'WebGL unavailable';
    containerEl.appendChild(msg);
    const noop = () => {};
    return { setState: noop, focus: noop, setView: noop, highlightCohort: noop, resize: noop };
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.autoUpdate = false;   // static city: re-render the shadow map only when something moved (see frame())
  renderer.shadowMap.type = THREE.PCFShadowMap; // r186 folds PCFSoftShadowMap into PCFShadowMap (already soft-filtered)
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.18;
  renderer.domElement.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;outline:none;touch-action:none';
  containerEl.appendChild(renderer.domElement);
  const canvas = renderer.domElement;

  const labelRenderer = new CSS2DRenderer();
  labelRenderer.domElement.style.cssText = 'position:absolute;inset:0;pointer-events:none;overflow:hidden';
  containerEl.appendChild(labelRenderer.domElement);
  const leaderSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  leaderSvg.setAttribute('style', 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;overflow:visible');
  labelRenderer.domElement.insertBefore(leaderSvg, labelRenderer.domElement.firstChild);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COL.bg);
  scene.fog = new THREE.FogExp2(VIEW.citizen.fog, VIEW.citizen.fogD);

  const camera = new THREE.PerspectiveCamera(33, 1, 1, 700);
  const HOME_TARGET = new THREE.Vector3(0, 3, 0);
  camera.position.set(95, 92, 112);

  const controls = new OrbitControls(camera, canvas);
  controls.target.copy(HOME_TARGET);
  controls.enableDamping = true; controls.dampingFactor = 0.07;
  controls.enablePan = false;
  controls.minDistance = 14; controls.maxDistance = 240;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.autoRotate = true; controls.autoRotateSpeed = 0;
  controls.update();

  // lights
  const keyLight = new THREE.DirectionalLight(VIEW.citizen.key, VIEW.citizen.keyI);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(2048, 2048);
  const sc = keyLight.shadow.camera; const SH = R * 1.28;
  sc.left = -SH; sc.right = SH; sc.top = SH; sc.bottom = -SH; sc.near = 20; sc.far = 420; sc.updateProjectionMatrix();
  keyLight.shadow.bias = -0.0004; keyLight.shadow.normalBias = 0.06; keyLight.shadow.radius = 3;
  scene.add(keyLight, keyLight.target);
  const hemi = new THREE.HemisphereLight(VIEW.citizen.sky, VIEW.citizen.ground, VIEW.citizen.hemiI);
  scene.add(hemi);

  // ---- shared materials ---------------------------------------------------------------------
  const matBuilding = new THREE.MeshStandardMaterial({ color: COL.building, roughness: 0.9, metalness: 0 });
  const matPlinth = new THREE.MeshStandardMaterial({ color: COL.plinth, roughness: 0.92, metalness: 0 });
  const matBed = new THREE.MeshStandardMaterial({ color: '#B8B9B5', roughness: 0.85, metalness: 0 });
  const matBase = new THREE.MeshStandardMaterial({ color: '#8C8D8A', roughness: 0.95, metalness: 0 });

  // ---- world state --------------------------------------------------------------------------
  const world = new THREE.Group(); scene.add(world);
  let builtKey = null;
  let cityGroup = null;
  let lastState = null;
  let viewTarget = 'citizen', viewT = 0;          // viewT: 0 citizen .. 1 system
  let cohortHL = null;
  let selectedRid = null;
  let clock = 0;
  let blocks = [], blockByKey = new Map();
  let landmarks = new Map();                       // place_id -> { pos, top, mesh, kind, name, label }
  let landmarkMeshes = [];
  let river = null;                                // { pts:[{x,z,hw}] }
  let tiles = null, tileCur = null, tileTgt = null, tileAnim = 0;
  let crowd = null, crowdAgents = [];
  let tower = { node: null, pos: new THREE.Vector3(0, 39, 0) };
  const subjects = new Map();                      // rid -> subject object
  const subjectGroup = new THREE.Group(); scene.add(subjectGroup);
  const threadGroup = new THREE.Group(); scene.add(threadGroup);

  // ===========================================================================================
  // City build (once per run)
  // ===========================================================================================
  function disposeCity() {
    if (!cityGroup) return;
    cityGroup.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
    world.remove(cityGroup);
    for (const lm of landmarks.values()) if (lm.label) lm.label.removeFromParent();
    cityGroup = null; landmarks = new Map(); landmarkMeshes = [];
  }

  function buildCity(state) {
    disposeCity();
    const city = state.city || {}, geo = state.geo || {};
    const rng = mulberry32(hashStr(`${state.seed}|${city.name}`));
    const districts = city.districts || [];
    const arcs = geo.district_arcs || {};
    const placePolar = geo.place_polar || {};
    cityGroup = new THREE.Group(); world.add(cityGroup);

    // ---- river (riverside district) -------------------------------------------------------
    const riverD = districts.find((d) => d.character === 'riverside');
    river = null;
    if (riverD && arcs[riverD.district_id]) {
      const arc = arcs[riverD.district_id];
      let span = normDeg(arc[1] - arc[0]); if (span === 0) span = 360;
      const mid = arc[0] + span / 2;
      const under = (city.landmarks || []).find((l) => l.kind === 'underpass');
      const qp = under && placePolar[under.place_id] ? placePolar[under.place_id] : [mid, 0.62];
      const Q = polarToXZ(qp[0], qp[1]);
      const E1 = polarToXZ(mid - 40, 0.99), E2 = polarToXZ(mid + 40, 0.99);
      const C = { x: 2 * Q.x - 0.5 * (E1.x + E2.x), z: 2 * Q.z - 0.5 * (E1.z + E2.z) };
      const pts = [];
      const N = 44;
      for (let i = 0; i <= N; i++) {
        const t = i / N, u = 1 - t;
        const x = u * u * E1.x + 2 * u * t * C.x + t * t * E2.x;
        const z = u * u * E1.z + 2 * u * t * C.z + t * t * E2.z;
        const hw = 1.5 + 1.9 * Math.sin(Math.PI * t) ** 0.6;
        pts.push({ x, z, hw });
      }
      river = { pts, Q };
    }
    const riverDist = (x, z) => {
      if (!river) return 99;
      let m = 99;
      for (const p of river.pts) { const d = Math.hypot(x - p.x, z - p.z) - p.hw; if (d < m) m = d; }
      return m;
    };
    world.userData.riverDist = riverDist;

    // ---- plinth (circle with closed river channel cut in) --------------------------------------
    const Rp = R + 1.0;
    const shape = new THREE.Shape();
    shape.absarc(0, 0, Rp, 0, Math.PI * 2, false);
    let bedGeo = null;
    if (river) {
      const left = [], right = [];
      for (let i = 0; i < river.pts.length; i++) {
        const p = river.pts[i], a = river.pts[Math.max(0, i - 1)], b = river.pts[Math.min(river.pts.length - 1, i + 1)];
        let tx = b.x - a.x, tz = b.z - a.z; const l = Math.hypot(tx, tz) || 1; tx /= l; tz /= l;
        left.push([p.x - tz * p.hw, -(p.z + tx * p.hw)]);
        right.push([p.x + tz * p.hw, -(p.z - tx * p.hw)]);
      }
      const loop = left.concat(right.reverse());
      const hole = new THREE.Path(); hole.moveTo(loop[0][0], loop[0][1]);
      for (let i = 1; i < loop.length; i++) hole.lineTo(loop[i][0], loop[i][1]);
      hole.closePath();
      shape.holes.push(hole);
      const bs = new THREE.Shape(); bs.moveTo(loop[0][0], loop[0][1]);
      for (let i = 1; i < loop.length; i++) bs.lineTo(loop[i][0], loop[i][1]);
      bedGeo = new THREE.ShapeGeometry(bs).rotateX(-Math.PI / 2);
    }
    const plinthDepth = 2.6;
    const plinthGeo = new THREE.ExtrudeGeometry(shape, { depth: plinthDepth, bevelEnabled: false, curveSegments: 96 })
      .rotateX(-Math.PI / 2).translate(0, -plinthDepth, 0);
    const plinth = new THREE.Mesh(plinthGeo, matPlinth);
    plinth.receiveShadow = true; plinth.castShadow = true;
    cityGroup.add(plinth);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(Rp + 2.2, Rp + 2.6, 0.9, 96).translate(0, -plinthDepth - 0.45, 0), matBase);
    cityGroup.add(base);
    if (bedGeo) {
      const bed = new THREE.Mesh(bedGeo.translate(0, -1.35, 0), matBed);
      bed.receiveShadow = true; cityGroup.add(bed);
    }

    // ---- blocks ---------------------------------------------------------------------------
    blocks = []; blockByKey = new Map();
    const half = (GRID - 1) / 2;
    const civicD = districts.find((d) => d.character === 'civic') || districts[0];
    for (let iz = -half; iz <= half; iz++) {
      for (let ix = -half; ix <= half; ix++) {
        const cx = ix * PITCH, cz = iz * PITCH;
        const hb = BLOCK / 2;
        const far = Math.max(Math.hypot(cx + hb, cz + hb), Math.hypot(cx - hb, cz + hb), Math.hypot(cx + hb, cz - hb), Math.hypot(cx - hb, cz - hb));
        if (far > R - 1.0) continue;
        const isRiver = river && (riverDist(cx, cz) < hb + 0.9 || riverDist(cx + hb, cz + hb) < 0.2 || riverDist(cx - hb, cz + hb) < 0.2 ||
          riverDist(cx + hb, cz - hb) < 0.2 || riverDist(cx - hb, cz - hb) < 0.2);
        if (isRiver) continue;
        const rr = Math.hypot(cx, cz);
        const bearing = normDeg(Math.atan2(cx, -cz) / DEG);
        let did = null;
        if (ix === 0 && iz === 0) did = civicD ? civicD.district_id : null;
        else {
          let best = null, bd = 1e9;
          for (const d of districts) {
            const a = arcs[d.district_id]; if (!a) continue;
            if (inArc(bearing, a)) { best = d; break; }
            const dd = arcDist(bearing, a); if (dd < bd) { bd = dd; best = d; }
          }
          did = best ? best.district_id : null;
        }
        const dist = districts.find((d) => d.district_id === did);
        const b = { ix, iz, cx, cz, r: rr, rn: rr / R, bearing, did, character: dist ? dist.character : 'residential', used: null };
        blocks.push(b); blockByKey.set(`${ix},${iz}`, b);
      }
    }
    const centre = blockByKey.get('0,0');
    if (centre) centre.used = 'plaza';

    // ---- landmarks --------------------------------------------------------------------------
    const lmList = (city.landmarks || []).slice().sort((a, b) => (a.kind === 'council' ? -1 : 0) - (b.kind === 'council' ? -1 : 0));
    for (const lm of lmList) {
      const pp = placePolar[lm.place_id] || [0, 0];
      const t = polarToXZ(pp[0], pp[1]);
      let pos = null, rot = 0, blk = null;
      if (lm.kind === 'underpass' && river) {
        // snap onto the river centreline nearest the target and span the channel
        let bi = 0, bd = 1e9;
        river.pts.forEach((p, i) => { const d = Math.hypot(p.x - t.x, p.z - t.z); if (d < bd) { bd = d; bi = i; } });
        const p = river.pts[bi], a = river.pts[Math.max(0, bi - 1)], b = river.pts[Math.min(river.pts.length - 1, bi + 1)];
        const tx = b.x - a.x, tz = b.z - a.z;
        pos = new THREE.Vector3(p.x, 0, p.z);
        // geometry spans local z; river tangent is local x => rotate so local z aligns with the normal
        rot = Math.atan2(-tz, tx); // local +z -> river normal (-tz, tx)
      } else if (lm.kind === 'council') {
        blk = centre;
      } else {
        let bd = 1e9;
        for (const b of blocks) {
          if (b.used) continue;
          const d = Math.hypot(b.cx - t.x, b.cz - t.z);
          if (d < bd) { bd = d; blk = b; }
        }
      }
      if (blk) {
        blk.used = 'landmark';
        pos = new THREE.Vector3(blk.cx, 0, blk.cz);
        const dx = -blk.cx, dz = -blk.cz;
        rot = lm.kind === 'council' ? 0 : Math.round(Math.atan2(dx, dz) / (Math.PI / 2)) * (Math.PI / 2);
      }
      if (!pos) continue;
      const { geo: g, top } = buildLandmarkGeometry(lm.kind, rng);
      const mesh = new THREE.Mesh(g, matBuilding);
      mesh.position.set(pos.x, blk ? PAD_H : 0, pos.z); mesh.rotation.y = rot;
      mesh.castShadow = true; mesh.receiveShadow = true;
      mesh.userData.placeId = lm.place_id;
      cityGroup.add(mesh); landmarkMeshes.push(mesh);
      landmarks.set(lm.place_id, { pos: new THREE.Vector3(pos.x, top + (blk ? PAD_H : 0), pos.z), base: pos.clone(), top, mesh, kind: lm.kind, name: lm.name, label: null });
      if (lm.kind === 'council') tower.pos.set(pos.x, top + 1.35, pos.z);
    }
    // landmarks that never got a position (no place_polar) fall back to nothing.

    // ---- ordinary buildings (instanced) ----------------------------------------------------
    const boxList = [], cylList = [];
    for (const b of blocks) {
      boxList.push({ x: b.cx, y: PAD_H / 2, z: b.cz, w: BLOCK, h: PAD_H, d: BLOCK, tone: 1 });
      if (b.used) continue;
      const jit = (a) => (rng() - 0.5) * a;
      const add = (x, z, w, h, d, tone) => boxList.push({ x: b.cx + x, y: PAD_H + h / 2, z: b.cz + z, w, h, d, tone: tone ?? (0.95 + rng() * 0.05) });
      switch (b.character) {
        case 'civic': {
          const hh = 4 + rng() * 4;
          add(0, -1.7 + jit(0.4), 6.8, hh, 2.5);
          if (rng() < 0.8) add(-1.6, 1.6, 2.6, hh * (0.7 + rng() * 0.3), 3.0);
          if (rng() < 0.5) add(2.4, 1.8, 2.2, hh * 0.6, 2.2);
          break;
        }
        case 'commercial': {
          const cells = [[-1.9, -1.9], [1.9, -1.9], [-1.9, 1.9], [1.9, 1.9]];
          const nearCore = clamp(1 - b.rn * 1.15, 0.05, 1);
          for (const [x, z] of cells) {
            if (rng() < 0.18) continue;
            const hh = 3 + nearCore * 15 * (0.55 + rng() * 0.45) + rng() * 2.5;
            const w = 3.0 + rng() * 0.6, d = 3.0 + rng() * 0.6;
            if (rng() < 0.12 && hh > 8) cylList.push({ x: b.cx + x, z: b.cz + z, r: 1.6, h: hh });
            else add(x + jit(0.3), z + jit(0.3), w, hh, d);
          }
          break;
        }
        case 'industrial': {
          add(-0.3, -2.2, 6.8, 2 + rng() * 1.2, 2.5);
          add(-0.3, 0.5, 6.8, 2 + rng() * 1.2, 2.3);
          if (rng() < 0.6) add(-1.8, 2.8, 3.2, 1.4, 1.5);
          const ns = 1 + Math.floor(rng() * 3);
          for (let i = 0; i < ns; i++) cylList.push({ x: b.cx + 2.9, z: b.cz + 2.5 - i * 2.0, r: 0.85, h: 5 + rng() * 2 });
          break;
        }
        case 'riverside': {
          const n = 2 + Math.floor(rng() * 2);
          for (let i = 0; i < n; i++) add(-2.2 + i * 2.3 + jit(0.4), jit(3.5), 2.0 + rng(), 1.2 + rng() * 1.5, 2.4 + rng());
          break;
        }
        case 'outskirts': {
          if (rng() < 0.4) break;
          const n = 1 + Math.floor(rng() * 2);
          for (let i = 0; i < n; i++) add(-1.8 + i * 3.4 + jit(1), jit(3), 2.4 + rng() * 0.8, 1.5 + rng() * 0.9, 2.0 + rng() * 0.8);
          break;
        }
        default: { // residential
          const cols = 3, rows = 2;
          for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
            if (rng() < 0.22) continue;
            const hh = 1.5 + rng() * 2.0 + (rng() < 0.12 ? 2 : 0);
            add(-2.4 + c * 2.4 + jit(0.3), -1.9 + r * 3.8 + jit(0.3), 1.9 + rng() * 0.5, hh, 2.3 + rng() * 0.6);
          }
        }
      }
    }
    // council plaza: low paved rings are implied by the pad; add a plaza step
    if (centre) boxList.push({ x: centre.cx, y: PAD_H + 0.05, z: centre.cz, w: 0.1, h: 0.1, d: 0.1, tone: 1 });

    const boxMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), matBuilding, boxList.length);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sv = new THREE.Vector3(), pv = new THREE.Vector3(), cc = new THREE.Color();
    boxList.forEach((o, i) => {
      m4.compose(pv.set(o.x, o.y, o.z), q, sv.set(o.w, o.h, o.d)); boxMesh.setMatrixAt(i, m4);
      boxMesh.setColorAt(i, cc.setScalar(o.tone));
    });
    boxMesh.castShadow = true; boxMesh.receiveShadow = true; boxMesh.frustumCulled = false;
    cityGroup.add(boxMesh);
    const cylMesh = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1, 1, 20), matBuilding, Math.max(1, cylList.length));
    cylList.forEach((o, i) => { m4.compose(pv.set(o.x, PAD_H + o.h / 2, o.z), q, sv.set(o.r, o.h, o.r)); cylMesh.setMatrixAt(i, m4); });
    cylMesh.count = cylList.length; cylMesh.castShadow = true; cylMesh.receiveShadow = true; cylMesh.frustumCulled = false;
    cityGroup.add(cylMesh);

    // ---- dissent tiles (one instanced plane, per block) -----------------------------------------
    const tileGeo = new THREE.PlaneGeometry(BLOCK + 1.6, BLOCK + 1.6).rotateX(-Math.PI / 2);
    tiles = new THREE.InstancedMesh(tileGeo, new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0, depthWrite: false, fog: false, toneMapped: false }), blocks.length);
    blocks.forEach((b, i) => { m4.compose(pv.set(b.cx, PAD_H + 0.02, b.cz), q, sv.set(1, 1, 1)); tiles.setMatrixAt(i, m4); tiles.setColorAt(i, cc.set(COL.plinth)); });
    tiles.frustumCulled = false; tiles.renderOrder = 1; tiles.visible = false;
    cityGroup.add(tiles);
    tileCur = blocks.map(() => new THREE.Color(COL.plinth));
    tileTgt = blocks.map(() => new THREE.Color(COL.plinth));

    // ---- tower node ---------------------------------------------------------------------------
    const node = new THREE.Mesh(new THREE.SphereGeometry(0.95, 24, 16), new THREE.MeshBasicMaterial({ color: COL.cyan, transparent: true, fog: false, toneMapped: false }));
    node.position.copy(tower.pos);
    cityGroup.add(node); tower.node = node;

    // ---- crowd ---------------------------------------------------------------------------------
    const nCrowd = 60;
    const cGeo = new THREE.BufferGeometry();
    cGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(nCrowd * 3), 3));
    cGeo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(nCrowd * 3).fill(0.5), 3));
    crowd = new THREE.Points(cGeo, new THREE.PointsMaterial({ size: 7, sizeAttenuation: false, map: dotTex(),
      vertexColors: true, transparent: true, depthWrite: false, toneMapped: false, fog: false }));
    crowd.frustumCulled = false; crowd.renderOrder = 4;
    crowdAgents = [];
    const cr = mulberry32(hashStr(`${state.seed}|${city.name}|crowd`));
    for (let i = 0; i < nCrowd; i++) {
      const horiz = cr() < 0.5;
      const k = Math.floor(cr() * (GRID + 1)) - Math.floor(GRID / 2) - 1;   // gap index -5..4
      const c = (k + 0.5) * PITCH + (cr() < 0.5 ? -0.55 : 0.55);
      const L = Math.sqrt(Math.max(4, (R - 3) ** 2 - c * c));
      crowdAgents.push({ horiz, c, L, s: (cr() * 2 - 1) * L, dir: cr() < 0.5 ? -1 : 1, v: 0.35 + cr() * 0.7, pause: 0,
                         tw: cr(), twRate: 0.25 + cr() * 0.5 });
    }
    cityGroup.add(crowd);

    // initial block assignment of dissent: filled in setState
    builtKey = `${state.seed}|${city.name}`;
  }

  // ===========================================================================================
  // Subjects
  // ===========================================================================================
  function ensureSubject(rid, idx) {
    let s = subjects.get(rid);
    if (s) return s;
    const group = new THREE.Group(); subjectGroup.add(group);
    // beacon dot: unlit core + soft halo that flashes on each blink
    const solid = new THREE.Group(); solid.position.y = DOT_Y;
    const core = new THREE.Sprite(new THREE.SpriteMaterial({ map: dotTex(), transparent: true, opacity: 1,
      sizeAttenuation: false, depthWrite: false, toneMapped: false, fog: false }));
    core.scale.setScalar(DOT_PX); core.renderOrder = 6;
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex(), transparent: true, opacity: 0,
      sizeAttenuation: false, depthWrite: false, toneMapped: false, fog: false }));
    halo.scale.setScalar(HALO_PX); halo.renderOrder = 5;
    solid.add(core, halo);
    const wire = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(DOT_R * 1.15, 1)),
      new THREE.LineBasicMaterial({ color: '#F4F4F0', transparent: true, opacity: 1 }));
    wire.position.y = DOT_Y; wire.visible = false;
    const ring = new THREE.Mesh(new THREE.RingGeometry(1.35, 1.7, 48), new THREE.MeshBasicMaterial({ color: COL.white, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide, fog: false, toneMapped: false }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = PAD_H + 0.12; ring.renderOrder = 2;
    group.add(solid, wire, ring);
    // label + leader
    // label: zero-size CSS2D anchor at the capsule top; the visible box is offset in screen space by the
    // de-overlap layout, and a 1px SVG leader joins the two.
    const anchor = document.createElement('div'); anchor.className = 'rh-anchor';
    const el = document.createElement('div'); el.className = 'rh-label'; el.textContent = rid;
    el.addEventListener('pointerdown', (e) => e.stopPropagation());
    el.addEventListener('click', (e) => { e.stopPropagation(); if (onSelect) onSelect(rid); });
    anchor.appendChild(el);
    const label = new CSS2DObject(anchor);
    label.position.set(0, DOT_TOP, 0);
    group.add(label);
    const leader = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    leader.setAttribute('stroke', 'rgba(230,238,255,0.55)'); leader.setAttribute('stroke-width', '1');
    leaderSvg.appendChild(leader);
    // thread + pulse
    const tGeo = new THREE.BufferGeometry();
    tGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(THREAD_SAMPLES * 3), 3));
    const thread = new THREE.Line(tGeo, new THREE.LineBasicMaterial({ color: COL.cyan, transparent: true, opacity: 0, fog: false, toneMapped: false }));
    thread.frustumCulled = false; thread.renderOrder = 3;
    threadGroup.add(thread);
    const pulse = new THREE.Mesh(new THREE.SphereGeometry(0.42, 12, 8), new THREE.MeshBasicMaterial({ color: COL.cyan, transparent: true, opacity: 1, fog: false, toneMapped: false }));
    pulse.visible = false; pulse.renderOrder = 4; threadGroup.add(pulse);

    s = {
      rid, idx, group, solid, core, halo, wire, ring, label, leader, thread, pulse, el,
      blinkPh: (idx * 0.618) % 1,
      pos: new THREE.Vector3(), from: new THREE.Vector3(), to: new THREE.Vector3(), moveT: 1, placed: false,
      mode: 'gone', tMode: 0, status: null,
      risk: 0, riskTgt: new THREE.Color(COL.white), riskCur: new THREE.Color(COL.white), rung: 0, ringW: 0,
      cohort: null,
      route: null,                                     // current control points (5 Vector3), lazily created
      routeTgt: null, routeT: 1, routeFrom: null, landmarkPlace: null, hasInterv: false,
      pulseT: -1, pulseDelay: 0,
      curve: null, retract: 0,
      ringOp: 1,
    };
    subjects.set(rid, s);
    return s;
  }

  function resolveSubjectXZ(x, z) {
    // keep capsules on the street gaps: push out of any block footprint
    for (const b of blocks) {
      const dx = x - b.cx, dz = z - b.cz;
      const lim = BLOCK / 2 + 0.55;
      if (Math.abs(dx) < lim && Math.abs(dz) < lim) {
        if (Math.abs(dx) >= Math.abs(dz)) x = b.cx + Math.sign(dx || 1) * STREET_C;
        else z = b.cz + Math.sign(dz || 1) * STREET_C;
        break;
      }
    }
    if (river) { const d = world.userData.riverDist(x, z); if (d < 0.8) { /* nudge to bank */ let bi = 0, bd = 1e9; river.pts.forEach((p, i) => { const dd = Math.hypot(p.x - x, p.z - z); if (dd < bd) { bd = dd; bi = i; } }); const p = river.pts[bi]; const l = Math.hypot(x - p.x, z - p.z) || 1; x = p.x + (x - p.x) / l * (p.hw + 1.2); z = p.z + (z - p.z) / l * (p.hw + 1.2); } }
    return { x, z };
  }

  function baseRoute(S, out) {
    const N = tower.pos; const d = Math.hypot(S.x - N.x, S.z - N.z);
    const M = new THREE.Vector3((S.x + N.x) / 2, (S.y + N.y) / 2 + 3 + d * 0.28, (S.z + N.z) / 2);
    return routeThrough(S, M, out);
  }
  function routeThrough(S, M, out) {
    const N = tower.pos;
    const lift = (a, b) => 1.5 + 0.22 * a.distanceTo(b);
    const A = new THREE.Vector3().lerpVectors(S, M, 0.5); A.y += lift(S, M);
    const B = new THREE.Vector3().lerpVectors(M, N, 0.5); B.y += lift(M, N);
    const pts = out || [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
    pts[0].copy(S); pts[1].copy(A); pts[2].copy(M); pts[3].copy(B); pts[4].copy(N);
    return pts;
  }
  function subjectTop(s, out = new THREE.Vector3()) { return out.set(s.pos.x, DOT_TOP + 0.1, s.pos.z); }

  function targetRoute(s) {
    const S = subjectTop(s);
    if (s.landmarkPlace && landmarks.has(s.landmarkPlace)) {
      const lm = landmarks.get(s.landmarkPlace);
      const M = lm.pos.clone(); M.y += 1.6;
      return routeThrough(S, M);
    }
    return baseRoute(S);
  }

  // ===========================================================================================
  // setState
  // ===========================================================================================
  function latestRung(rs, planIv) {
    const arr = rs.interventions_applied || [];
    let r = arr.length ? (arr[arr.length - 1].rung || 0) : 0;
    if (planIv && planIv.rung > r) r = planIv.rung;
    return r;
  }

  function setState(state, { animate = true } = {}) {
    if (!state || !state.city || !state.geo) return;
    const key = `${state.seed}|${state.city.name}`;
    if (key !== builtKey) {
      buildCity(state);
      for (const s of subjects.values()) { subjectGroup.remove(s.group); threadGroup.remove(s.thread); threadGroup.remove(s.pulse); s.label.removeFromParent(); s.leader.remove(); }
      subjects.clear();
    }
    lastState = state;
    const geo = state.geo;

    // interventions this tick
    const ivBy = new Map();
    for (const iv of (state.plan && state.plan.interventions) || []) {
      const cur = ivBy.get(iv.resident_id);
      if (!cur || (iv.rung || 0) >= (cur.rung || 0)) ivBy.set(iv.resident_id, iv);
    }

    // resolve subject positions (with relaxation so shared places do not overlap)
    const rstates = state.resident_states || [];
    const xz = new Map();
    for (const rs of rstates) {
      const pp = geo.resident_polar && geo.resident_polar[rs.resident_id];
      if (!pp) continue;
      const p = polarToXZ(pp[0], pp[1]);
      xz.set(rs.resident_id, resolveSubjectXZ(p.x, p.z));
    }
    const ids = [...xz.keys()];
    for (let it = 0; it < 6; it++) {
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const a = xz.get(ids[i]), b = xz.get(ids[j]);
        const dx = b.x - a.x, dz = b.z - a.z, d = Math.hypot(dx, dz);
        if (d < 1.6) {
          // slide along the street axis
          const alongX = Math.abs(((a.z % PITCH) + PITCH) % PITCH - STREET_C) < Math.abs(((a.x % PITCH) + PITCH) % PITCH - STREET_C);
          const push = (1.6 - d) / 2 + 0.05;
          if (alongX) { a.x -= push; b.x += push; } else { a.z -= push; b.z += push; }
        }
      }
    }

    rstates.forEach((rs, idx) => {
      const rid = rs.resident_id;
      const s = ensureSubject(rid, idx);
      const p = rs.prediction || {};
      const target = xz.get(rid);
      const reassigned = rs.status === 'reassigned';

      // label text
      const dev = p.deviation_risk != null ? p.deviation_risk : 0;
      buildSubjectLabel(s, rid, residentName(state, rid), reassigned, p, dev);
      s.cohort = p.cohort || null;
      s.risk = dev; riskColor(dev, s.riskTgt);
      const iv = ivBy.get(rid);
      s.rung = latestRung(rs, iv);
      rebuildRing(s);
      s.hasInterv = !!(iv && iv.place_id);
      s.landmarkPlace = iv && iv.place_id ? iv.place_id : null;

      // position tween
      if (target) {
        const nt = new THREE.Vector3(target.x, 0, target.z);
        if (!s.placed || !animate) { s.pos.copy(nt); s.from.copy(nt); s.to.copy(nt); s.moveT = 1; s.placed = true; }
        else if (s.to.distanceToSquared(nt) > 0.01) { s.from.copy(s.pos); s.to.copy(nt); s.moveT = 0; }
        if (!s.placed) s.placed = true;
      }

      // mode
      const prev = s.mode;
      if (reassigned) {
        if (prev === 'active') { s.mode = 'retiring'; s.tMode = 0; }
        else if (prev === 'gone' && s.status === null && animate) { s.mode = 'retiring'; s.tMode = 1.0; s.retract = 1; }  // loaded already retired: brief ghost
        else if (prev === 'gone') s.mode = 'gone';
        if (!animate && s.mode === 'retiring') s.mode = 'gone';
      } else if (prev !== 'active') {
        s.mode = 'active'; s.tMode = 0; s.solid.visible = true; s.wire.visible = false; s.wire.material.opacity = 1;
        if (prev === 'gone' && s.status !== null) s.retract = 1;   // returning from retirement: thread grows back out
      }
      s.status = rs.status;

      // thread route
      s.routeFrom = s.route ? s.route.map((v) => v.clone()) : null;
      s.routeTgt = targetRoute(s);
      if (!s.route) { s.route = s.routeTgt.map((v) => v.clone()); s.routeT = 1; if (animate) { s.route = baseRoute(subjectTop(s)).map((v) => v.clone()); s.routeFrom = s.route.map((v) => v.clone()); s.routeT = 0; } }
      else if (animate) s.routeT = 0; else s.routeT = 1;
      if (!animate) s.route = s.routeTgt.map((v) => v.clone());
      s.pulseT = s.hasInterv ? -(animate ? 0.7 : 1.5) : -1;
      s.pulseCycle = 5.5;
    });

    // dissent tiles
    const dis = state.district_dissent || {};
    blocks.forEach((b, i) => {
      const v = dis[b.did] != null ? dis[b.did] : 0;
      tileTgt[i].set(COL.plinth).lerp(riskColor(v, new THREE.Color()), smooth(0.12, 0.5, v));
      if (!animate) { tileCur[i].copy(tileTgt[i]); }
    });
    tileAnim = animate ? 1.2 : 0.05;

    // landmark labels for intervention places
    const placeCount = new Map();
    for (const iv of ivBy.values()) if (iv.place_id) placeCount.set(iv.place_id, (placeCount.get(iv.place_id) || 0) + 1);
    for (const [pid, lm] of landmarks) {
      const used = placeCount.has(pid);
      if (used && !lm.label) {
        const anc = document.createElement('div'); anc.className = 'rh-anchor';
        const el = document.createElement('div'); el.className = 'rh-label rh-lm'; el.textContent = lm.name.toUpperCase(); el.dataset.tip = 'landmark';
        el.addEventListener('pointerdown', (e) => e.stopPropagation());
        el.addEventListener('click', (e) => { e.stopPropagation(); flyToLandmark(pid); });
        anc.appendChild(el);
        lm.label = new CSS2DObject(anc); lm.label.element = anc; lm.label.position.set(lm.base.x, 0.3, lm.base.z);
        cityGroup.add(lm.label);
      }
      if (lm.label) lm.label.userData.used = used;
    }
    applyRings();
  }

  function residentName(state, rid) {
    const r = (state.residents || []).find((x) => x.resident_id === rid);
    const full = r && r.name ? String(r.name).trim() : '';
    if (!full) return { last: rid.toUpperCase(), first: '' };
    const parts = full.split(/\s+/);
    if (parts.length === 1) return { last: parts[0].toUpperCase(), first: '' };
    return { last: parts[parts.length - 1].toUpperCase(), first: parts.slice(0, -1).join(' ') };
  }

  function lblSpan(cls, text, tip, parent) {
    const e = document.createElement('span');
    if (cls) e.className = cls;
    e.textContent = text;
    if (tip) e.dataset.tip = tip;
    parent.appendChild(e);
    return e;
  }

  // two-line label: line 1 = SURNAME, First + dim id; line 2 = RISK / TIER / death year (or REASSIGNED)
  function buildSubjectLabel(s, rid, nm, reassigned, p, dev) {
    const el = s.el;
    const l1 = document.createElement('div'); l1.className = 'rh-l1';
    lblSpan('rh-nm', nm.first ? `${nm.last}, ${nm.first}` : nm.last, 'subject', l1);
    lblSpan('rh-id', rid, null, l1);
    const l2 = document.createElement('div'); l2.className = 'rh-l2';
    if (reassigned) {
      lblSpan('rh-re', 'REASSIGNED', 'reassigned', l2);
    } else {
      const rk = lblSpan('rh-k', 'RISK ', 'risk', l2);
      const c = riskColor(dev, new THREE.Color());
      lblSpan('rh-rv', `${Math.round(dev * 100)}%`, 'risk', l2).style.color = '#' + c.getHexString();
      void rk;
      lblSpan('rh-sep', ' · ', null, l2);
      lblSpan('rh-k', `TIER ${p.classification || '?'}`, 'tier', l2);
      if (p.death_forecast && p.death_forecast.year != null) {
        lblSpan('rh-sep', ' · ', null, l2);
        lblSpan('rh-k', `† ${p.death_forecast.year}`, 'death', l2);
      }
    }
    el.replaceChildren(l1, l2);
    s.labelKey = (s.labelKey || 0) + 1;   // text changed: re-measure in layoutLabels
    s.lw = 0;
  }

  function rebuildRing(s) {
    const inner = 1.35, outer = 1.7 + 0.14 * s.rung + (s.rung >= 4 ? 0.1 : 0);
    if (s.ringW === outer) return;
    s.ringW = outer;
    s.ring.geometry.dispose();
    s.ring.geometry = new THREE.RingGeometry(inner, outer, 48);
  }

  function applyRings() { /* opacity evaluated per frame via cohortHL/selectedRid */ }

  // ===========================================================================================
  // Per-frame updates
  // ===========================================================================================
  const _v = new THREE.Vector3();
  const _haloWhite = new THREE.Color('#FFFFFF');
  function updateSubject(s, dt) {
    if (s.mode === 'gone') { s.group.visible = false; s.thread.visible = false; s.pulse.visible = false; s.label.visible = false; s.leader.style.display = 'none'; return; }
    s.group.visible = true;
    // movement
    if (s.moveT < 1) { s.moveT = Math.min(1, s.moveT + dt / 1.9); s.pos.lerpVectors(s.from, s.to, easeIO(s.moveT)); }
    s.group.position.set(s.pos.x, 0, s.pos.z);
    s.tMode += dt;
    const ov = viewT;
    let wireOp = 1, ringFade = 1, labelFade = 1;
    if (s.mode === 'retiring') {
      const t = s.tMode;
      s.solid.visible = t < 0.3; s.wire.visible = t >= 0.3 || true;
      s.wire.visible = t >= 0.2;
      s.retract = clamp((t - 0.2) / 1.5, 0, 1);
      ringFade = 1 - clamp((t - 0.2) / 1.5, 0, 1);
      wireOp = 1 - clamp((t - 1.7) / 1.3, 0, 1);
      labelFade = wireOp;
      s.wire.material.opacity = wireOp * 0.9;
      if (t > 3.0) { s.mode = 'gone'; return; }
    } else {
      s.retract = Math.max(0, s.retract - dt / 1.1);
    }

    // risk ring
    s.riskCur.lerp(s.riskTgt, Math.min(1, dt * 3));

    // blink: a beacon flash with a sharp attack and slow decay. Higher deviation risk blinks faster
    // (period 2.4s calm -> ~1.0s at risk 1); in System view the halo flash carries the risk colour.
    const sel0 = selectedRid === s.rid;
    s.blinkPh = (s.blinkPh + dt / (2.4 - 1.4 * clamp(s.risk || 0, 0, 1))) % 1;
    const flash = sel0 ? 0.7 + 0.3 * Math.sin(clock * 3) : Math.exp(-s.blinkPh * 7);
    s.core.material.opacity = 0.45 + 0.55 * flash;
    s.core.scale.setScalar(DOT_PX * (1 + 0.22 * flash));
    s.halo.material.color.copy(_haloWhite).lerp(s.riskCur, ov);
    s.halo.material.opacity = 0.75 * flash;
    s.halo.scale.setScalar(HALO_PX * (0.45 + 0.9 * (sel0 ? 0.5 : s.blinkPh)));
    s.ring.material.color.copy(s.riskCur);
    let ringOp = 0.95;
    if (cohortHL) ringOp = s.cohort === cohortHL ? 1 : 0.18;
    const hl = cohortHL && s.cohort === cohortHL;
    const sel = selectedRid === s.rid;
    const pulseK = hl || sel ? 1 + 0.08 * Math.sin(clock * 5) : 1;
    s.ring.scale.setScalar(hl ? 1.3 * pulseK : pulseK);
    s.ring.material.opacity = ringOp * ringFade * ov;
    s.ring.visible = ov > 0.01 && s.ring.material.opacity > 0.01;

    // label + leader
    s.label.visible = ov > 0.02 && labelFade > 0.02;
    s.labelOp = ov * labelFade * (cohortHL && !hl ? 0.35 : 1);
    s.el.style.opacity = String(s.labelOp);
    s.el.classList.toggle('rh-sel', sel);
    s.leader.style.display = s.label.visible ? '' : 'none';
    s.leader.style.opacity = String(s.labelOp);

    // thread
    if (s.route && s.routeTgt) {
      if (s.routeT < 1) s.routeT = Math.min(1, s.routeT + dt / 1.5);
      const e = easeIO(s.routeT);
      const live = targetRoute(s);   // endpoints follow the moving subject
      for (let i = 0; i < 5; i++) {
        const from = s.routeFrom ? s.routeFrom[i] : live[i];
        s.route[i].lerpVectors(from, live[i], e);
      }
      s.route[0].copy(live[0]);
      const rt = s.retract;
      const pts = rt > 0 ? s.route.map((p) => _v.clone().copy(p).lerp(tower.pos, rt)) : s.route;
      s.curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.5);
      const arr = s.thread.geometry.attributes.position.array;
      const samples = s.curve.getPoints(THREAD_SAMPLES - 1);
      for (let i = 0; i < THREAD_SAMPLES; i++) { arr[i * 3] = samples[i].x; arr[i * 3 + 1] = samples[i].y; arr[i * 3 + 2] = samples[i].z; }
      s.thread.geometry.attributes.position.needsUpdate = true;
      const tOp = ov * (cohortHL && s.cohort !== cohortHL ? 0.35 : 0.9) * (1 - smooth(0.92, 1, rt));
      s.thread.material.opacity = tOp;
      s.thread.visible = tOp > 0.01;
    }
    // pulse: tower -> subject along the thread, repeating while an intervention is live
    if (s.hasInterv && s.curve && s.mode === 'active' && ov > 0.05) {
      s.pulseT += dt;
      const cyc = s.pulseCycle || 5.5, dur = 2.0;
      if (s.pulseT < 0) s.pulse.visible = false;
      else {
        const ph = s.pulseT % cyc;
        if (ph < dur) {
          s.curve.getPoint(1 - easeIO(ph / dur), s.pulse.position);
          s.pulse.visible = true; s.pulse.material.opacity = ov;
        } else s.pulse.visible = false;
      }
    } else s.pulse.visible = false;
  }

  // label de-overlap: stack boxes upward from each capsule top in screen space, damped
  const _lv = new THREE.Vector3();
  function layoutLabels() {
    if (viewT < 0.02) return;
    const W = containerEl.clientWidth, H = containerEl.clientHeight;
    const items = [];
    for (const s of subjects.values()) {
      if (!s.label.visible) continue;
      _lv.set(s.pos.x, DOT_TOP, s.pos.z).project(camera);
      if (_lv.z > 1) { s.label.visible = false; continue; }
      const ax = (_lv.x * 0.5 + 0.5) * W, ay = (-_lv.y * 0.5 + 0.5) * H;
      if (!s.lw) { const ow = s.el.offsetWidth, oh = s.el.offsetHeight; if (ow > 0 && oh > 0) { s.lw = ow; s.lh = oh; } }
      const w = s.lw || 150, h = s.lh || 30;
      items.push({ s, ax, ay, w, h });
    }
    items.sort((a, b) => a.ay - b.ay);
    const placed = [];
    for (const it of items) {
      const cx = it.ax; let cy = it.ay - 30;
      for (let k = 0; k < 14; k++) {
        const hit = placed.find((p) => Math.abs(p.cx - cx) < (p.w + it.w) / 2 + 4 && Math.abs(p.cy - cy) < (p.h + it.h) / 2 + 3);
        if (!hit) break;
        cy = hit.cy - (hit.h + it.h) / 2 - 3;
      }
      placed.push({ cx, cy, w: it.w, h: it.h });
      const s = it.s;
      if (s.lx === undefined) { s.lx = cx - it.ax; s.ly = cy - it.ay; }
      s.lx += (cx - it.ax - s.lx) * 0.25; s.ly += (cy - it.ay - s.ly) * 0.25;
      s.el.style.transform = `translate(-50%,-50%) translate(${s.lx.toFixed(1)}px,${s.ly.toFixed(1)}px)`;
      s.leader.setAttribute('x1', it.ax.toFixed(1)); s.leader.setAttribute('y1', it.ay.toFixed(1));
      s.leader.setAttribute('x2', (it.ax + s.lx).toFixed(1)); s.leader.setAttribute('y2', (it.ay + s.ly + it.h / 2).toFixed(1));
    }
  }

  function updateCrowd(dt) {
    if (!crowd) return;
    const posA = crowd.geometry.attributes.position.array, colA = crowd.geometry.attributes.color.array;
    const rd = world.userData.riverDist;
    for (let i = 0; i < crowdAgents.length; i++) {
      const a = crowdAgents[i];
      if (a.pause > 0) a.pause -= dt;
      else {
        a.s += a.dir * a.v * dt;
        if (Math.abs(a.s) > a.L) { a.dir *= -1; a.s = clamp(a.s, -a.L, a.L); }
        if (Math.random() < dt * 0.02) a.pause = 1 + Math.random() * 3;
      }
      const x = a.horiz ? a.s : a.c, z = a.horiz ? a.c : a.s;
      if (river && rd(x, z) < 0.3) { a.dir *= -1; a.s += a.dir * a.v * dt * 3; }
      posA[i * 3] = x; posA[i * 3 + 1] = 0.35; posA[i * 3 + 2] = z;
      // twinkle: dim most of the time, a brief soft blink now and then
      a.tw = (a.tw + dt * a.twRate) % 1;
      const b = 0.3 + 0.7 * Math.exp(-a.tw * 10);
      colA[i * 3] = b; colA[i * 3 + 1] = b; colA[i * 3 + 2] = b * 0.98;
    }
    crowd.geometry.attributes.position.needsUpdate = true;
    crowd.geometry.attributes.color.needsUpdate = true;
  }

  function updateTiles(dt) {
    if (!tiles) return;
    const ov = viewT;
    tiles.material.opacity = 0.8 * ov;
    tiles.visible = ov > 0.01;
    if (tileAnim > 0) {
      tileAnim -= dt;
      const k = Math.min(1, dt * 2.6);
      for (let i = 0; i < tileCur.length; i++) { tileCur[i].lerp(tileTgt[i], k); tiles.setColorAt(i, tileCur[i]); }
      tiles.instanceColor.needsUpdate = true;
    }
  }

  // view tween -----------------------------------------------------------------------------------
  const _c1 = new THREE.Color(), _c2 = new THREE.Color();
  function updateView(dt) {
    const tgt = viewTarget === 'system' ? 1 : 0;
    if (viewT !== tgt) { viewT = viewT < tgt ? Math.min(tgt, viewT + dt / 1.0) : Math.max(tgt, viewT - dt / 1.0); }
    const e = easeIO(viewT), A = VIEW.citizen, B = VIEW.system;
    keyLight.color.copy(_c1.set(A.key).lerp(_c2.set(B.key), e));
    keyLight.intensity = lerp(A.keyI, B.keyI, e);
    const az = lerp(A.az, B.az, e) * DEG, el = lerp(A.el, B.el, e) * DEG, dist = 190;
    keyLight.position.set(Math.sin(az) * Math.cos(el) * dist, Math.sin(el) * dist, -Math.cos(az) * Math.cos(el) * dist);
    keyLight.target.position.set(0, 0, 0);
    hemi.color.copy(_c1.set(A.sky).lerp(_c2.set(B.sky), e));
    hemi.groundColor.copy(_c1.set(A.ground).lerp(_c2.set(B.ground), e));
    hemi.intensity = lerp(A.hemiI, B.hemiI, e);
    scene.fog.color.copy(_c1.set(A.fog).lerp(_c2.set(B.fog), e));
    scene.fog.density = lerp(A.fogD, B.fogD, e);
    scene.background.copy(_c1.set(A.bg).lerp(_c2.set(B.bg), e));
    if (tower.node) { tower.node.material.opacity = e; tower.node.visible = e > 0.01; const sc2 = 1 + 0.08 * Math.sin(clock * 2.4); tower.node.scale.setScalar(sc2); }
    for (const lm of landmarks.values()) if (lm.label) lm.label.visible = !!lm.label.userData.used && e > 0.02;
    for (const lm of landmarks.values()) if (lm.label) lm.label.element.firstChild.style.opacity = String(e);
  }

  // camera fly ------------------------------------------------------------------------------------
  let fly = null, autoMul = 0, idle = 3.0, userActive = false, focusedRid = null;
  function flyTo(pos, target, dur = 1.5) {
    fly = { t: 0, dur, p0: camera.position.clone(), t0: controls.target.clone(), p1: pos.clone(), t1: target.clone() };
    controls.enabled = false;
  }
  function updateCamera(dt) {
    if (fly) {
      fly.t += dt; const k = clamp(fly.t / fly.dur, 0, 1), e = easeIO(k);
      camera.position.lerpVectors(fly.p0, fly.p1, e); camera.position.y += Math.sin(Math.PI * e) * 6;
      controls.target.lerpVectors(fly.t0, fly.t1, e);
      if (k >= 1) { fly = null; controls.enabled = true; idle = 0; }
    }
    let wantAuto = !fly && !focusedRid && !userActive && idle > 4;
    if (!fly) idle += dt;
    autoMul += ((wantAuto ? 1 : 0) - autoMul) * Math.min(1, dt * (wantAuto ? 0.7 : 4));
    controls.autoRotateSpeed = 0.42 * autoMul;
    controls.update(dt);
  }
  controls.addEventListener('start', () => { userActive = true; idle = 0; if (fly) { fly = null; controls.enabled = true; } });
  controls.addEventListener('end', () => { userActive = false; idle = 0; });

  function frameFocusPose(p, tgtY, dist, height) {
    const out = new THREE.Vector3(p.x, 0, p.z);
    let d = out.clone().setY(0); if (d.length() < 2) d.set(0.3, 0, 1);
    d.normalize().applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.5);
    const pos = new THREE.Vector3(p.x, 0, p.z).addScaledVector(d, dist); pos.y = height;
    return { pos, target: new THREE.Vector3(p.x, tgtY, p.z) };
  }

  function focus(rid) {
    selectedRid = rid || null;
    focusedRid = null;
    if (rid) {
      const s = subjects.get(rid);
      if (s && s.mode !== 'gone') {
        const dest = s.to.lengthSq() ? s.to : s.pos;
        const f = frameFocusPose(dest, 3, 30, 27);
        focusedRid = rid; autoMul = 0;
        flyTo(f.pos, f.target, 1.5);
        return;
      }
    }
    // return to slow orbit
    const off = camera.position.clone().sub(controls.target);
    const az = Math.atan2(off.x, off.z);
    const dist = 150, pol = 0.98;
    const pos = new THREE.Vector3(Math.sin(pol) * Math.sin(az), Math.cos(pol), Math.sin(pol) * Math.cos(az)).multiplyScalar(dist).add(HOME_TARGET);
    flyTo(pos, HOME_TARGET, 1.6);
  }

  function flyToLandmark(pid) {
    const lm = landmarks.get(pid); if (!lm) return;
    focusedRid = '__lm__'; autoMul = 0;
    const f = frameFocusPose(lm.base, Math.min(lm.top * 0.45, 8), 26 + lm.top * 0.5, 16 + lm.top * 0.45);
    flyTo(f.pos, f.target, 1.5);
  }

  // picking -----------------------------------------------------------------------------------------
  const raycaster = new THREE.Raycaster();
  function pick(ev) {
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    let best = null, bd = 28;
    for (const s of subjects.values()) {
      if (s.mode !== 'active') continue;
      _v.set(s.pos.x, 1.6, s.pos.z).project(camera);
      if (_v.z > 1) continue;
      const sx = (_v.x * 0.5 + 0.5) * rect.width, sy = (-_v.y * 0.5 + 0.5) * rect.height;
      const d = Math.hypot(sx - mx, sy - my);
      if (d < bd) { bd = d; best = s; }
    }
    if (best) return { rid: best.rid };
    raycaster.setFromCamera(new THREE.Vector2((mx / rect.width) * 2 - 1, -(my / rect.height) * 2 + 1), camera);
    const hit = raycaster.intersectObjects(landmarkMeshes, false)[0];
    if (hit) return { place: hit.object.userData.placeId };
    return null;
  }
  let down = null, hoverT = 0;
  canvas.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY, t: performance.now() }; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y); down = null;
    if (moved > 5) return;
    const hit = pick(e);
    if (!hit) return;
    if (hit.rid) { if (onSelect) onSelect(hit.rid); }
    else if (hit.place) flyToLandmark(hit.place);
  });
  canvas.addEventListener('pointermove', (e) => {
    const now = performance.now(); if (now - hoverT < 80 || e.buttons) return; hoverT = now;
    canvas.style.cursor = pick(e) ? 'pointer' : 'default';
  });

  // ---- loop / lifecycle ---------------------------------------------------------------------------
  let frameNo = 0, raf = 0, last = 0, running = false, visible = true;
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, Math.max(0, (now - last) / 1000)); last = now; clock += dt;
    updateView(dt);
    updateCamera(dt);
    updateCrowd(dt);
    updateTiles(dt);
    for (const s of subjects.values()) updateSubject(s, dt);
    layoutLabels();
    frameNo++;
    let moving = viewT > 0 && viewT < 1 || (viewTarget === 'system') !== (viewT >= 1) || !!fly || frameNo < 3;
    if (!moving) for (const s of subjects.values()) if (s.moveT < 1 || s.mode === 'retiring') { moving = true; break; }
    renderer.shadowMap.needsUpdate = moving || frameNo % 8 === 0;   // crowd shadows refresh at ~7 Hz
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }
  function start() { if (running || !visible || document.hidden) return; running = true; last = performance.now(); raf = requestAnimationFrame(frame); }
  function stop() { running = false; cancelAnimationFrame(raf); }
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else start(); });
  if (typeof IntersectionObserver !== 'undefined') {
    new IntersectionObserver((es) => { visible = es[es.length - 1].isIntersecting; visible ? start() : stop(); }).observe(containerEl);
  }

  function resize() {
    const w = Math.max(1, containerEl.clientWidth), h = Math.max(1, containerEl.clientHeight);
    renderer.setSize(w, h, false); labelRenderer.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    // keep the whole plinth in frame on narrow stages
    controls.minDistance = 14;
  }
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(resize).observe(containerEl);
  window.addEventListener('resize', resize);
  resize(); start();

  // debug hook for tests (renderer stats)
  const api = {
    setState,
    focus,
    setView(view) { viewTarget = view === 'system' ? 'system' : 'citizen'; if (!lastState) viewT = viewTarget === 'system' ? 1 : 0; /* before first state: snap, no fade */ },
    highlightCohort(c) { cohortHL = c || null; },
    resize,
  };
  // test hook: step the simulation without rendering (headless software GL renders a frame in ~0.3 s)
  const advance = (sec) => {
    for (let t = 0; t < sec; t += 1 / 30) {
      clock += 1 / 30; updateView(1 / 30); updateCamera(1 / 30); updateCrowd(1 / 30); updateTiles(1 / 30);
      for (const s of subjects.values()) updateSubject(s, 1 / 30);
    }
    layoutLabels();
  };
  Object.defineProperty(api, '_debug', { enumerable: false, get: () => ({ renderer, scene, camera, controls, subjects, landmarks, advance, flyToLandmark }) });
  return api;
}

// ---------------------------------------------------------------------------------------------
function injectCSS() {
  if (document.getElementById('rh-world-css')) return;
  const st = document.createElement('style'); st.id = 'rh-world-css';
  st.textContent = `
.rh-anchor{width:0;height:0;pointer-events:none}
.rh-label{position:absolute;left:0;top:0;transform:translate(-50%,-50%);font:10px/1.35 ${MONO};letter-spacing:.04em;color:#E6EEFF;background:rgba(8,12,18,.82);
  border:1px solid rgba(111,231,255,.35);padding:3px 7px;white-space:nowrap;pointer-events:auto;cursor:pointer;user-select:none;opacity:0;
  -webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
.rh-label:hover{border-color:rgba(111,231,255,.7)}
.rh-label .rh-l1{display:flex;align-items:baseline;gap:6px}
.rh-label .rh-nm{font-weight:700;color:#F4F8FF}
.rh-label .rh-id{font-size:9px;color:rgba(230,238,255,.42)}
.rh-label .rh-l2{font-size:9px;color:rgba(230,238,255,.72)}
.rh-label .rh-sep{color:rgba(230,238,255,.3)}
.rh-label .rh-rv{font-weight:700}
.rh-label .rh-re{color:#8a93a0}
.rh-label.rh-sel{border-color:rgba(111,231,255,.95);background:rgba(8,12,18,.92)}
.rh-label.rh-sel::before,.rh-label.rh-sel::after{content:'';position:absolute;width:6px;height:6px;border:1px solid #6FE7FF;pointer-events:none}
.rh-label.rh-sel::before{left:-3px;top:-3px;border-right:0;border-bottom:0}
.rh-label.rh-sel::after{right:-3px;bottom:-3px;border-left:0;border-top:0}
.rh-label.rh-lm{transform:translate(-50%,0) translateY(14px);font-size:9px;color:#9aa5b5;background:rgba(8,12,18,.72)}
`;
  document.head.appendChild(st);
}
