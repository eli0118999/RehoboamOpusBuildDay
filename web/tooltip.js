// Hover tooltips for any element carrying data-tip="<glossary key>" (or data-tip-text="free text").
// One delegated listener on document, so dynamically created elements (cards, feed lines, 3D labels) just work.
import { tipText } from './glossary.js';

let box = null, current = null, showTimer = 0;

function ensureBox() {
  if (box) return box;
  box = document.createElement('div');
  box.id = 'tip';
  box.innerHTML = '<div class="tip-title"></div><div class="tip-body"></div>';
  document.body.appendChild(box);
  return box;
}

function contentFor(el) {
  if (el.dataset.tip) {
    const g = tipText(el.dataset.tip);
    const extra = el.dataset.tipText || el.dataset.tipTitle;   // element-specific detail, shown under the definition
    if (g && extra) return { title: g.title, body: `${extra}\n\n${g.body}` };
    if (g) return g;
  }
  if (el.dataset.tipText) return { title: el.dataset.tipTitle || '', body: el.dataset.tipText };
  return null;
}

function place(ev) {
  const b = ensureBox();
  const pad = 14, w = b.offsetWidth, h = b.offsetHeight;
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + w > innerWidth - 8) x = ev.clientX - w - pad;
  if (y + h > innerHeight - 8) y = ev.clientY - h - pad;
  b.style.transform = `translate(${Math.max(8, x)}px, ${Math.max(8, y)}px)`;
}

function hide() {
  clearTimeout(showTimer); current = null;
  if (box) box.classList.remove('show');
}

export function installTooltips() {
  document.addEventListener('mouseover', (ev) => {
    const el = ev.target.closest?.('[data-tip],[data-tip-text]');
    if (el === current) return;
    if (!el) return hide();
    const c = contentFor(el);
    if (!c) return hide();
    current = el;
    clearTimeout(showTimer);
    showTimer = setTimeout(() => {
      if (current !== el) return;
      const b = ensureBox();
      b.querySelector('.tip-title').textContent = c.title;
      b.querySelector('.tip-title').hidden = !c.title;
      b.querySelector('.tip-body').textContent = c.body;
      place(ev);
      b.classList.add('show');
    }, 220);
  });
  document.addEventListener('mousemove', (ev) => { if (current && box?.classList.contains('show')) place(ev); });
  document.addEventListener('mousedown', hide);
  document.addEventListener('scroll', hide, true);
  window.addEventListener('blur', hide);
}
