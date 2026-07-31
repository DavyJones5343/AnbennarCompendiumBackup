/**
 * Print a random sample of rendered requirement lines, for eyeballing that
 * mission text reads as English. Run: node sample_lines.js
 */
const fs = require('fs'), path = require('path'), vm = require('vm');
const dir = __dirname;
const html = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
const load = f => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
const code = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]).sort((a, b) => b.length - a.length)[0];

const stub = () => new Proxy(function () {}, {
  get: (t, p) => ['style', 'classList', 'dataset'].includes(p) ? stub()
    : (p === 'textContent' || p === 'innerHTML' || p === 'value') ? ''
    : (p === Symbol.toPrimitive || p === 'toString') ? () => '' : stub(),
  set: () => true, apply: () => stub(),
});
const sb = {
  console,
  document: { body: stub(), head: stub(), documentElement: stub(),
    getElementById: () => stub(), querySelector: () => stub(),
    querySelectorAll: () => [], addEventListener() {}, createElement: () => stub() },
  window: { addEventListener() {}, matchMedia: () => ({ matches: false }) },
  localStorage: { getItem: () => null, setItem() {} },
  fetch: () => Promise.reject(new Error('no network')), setTimeout, clearTimeout,
  Image: function () {},
};
sb.window.document = sb.document;
vm.createContext(sb);
vm.runInContext(code, sb, { filename: 'index-inline.js' });

Object.assign(sb, {
  DATA: load('anbennar_data.json'), TRIGGERS: load('mission_triggers.json'),
  PROVINCES: load('province_names.json'), MODIFIERS: load('modifiers_data.json'),
  EVENT_NAMES: load('event_names.json'), SCRIPTED: load('scripted_defs.json'),
  NAMES: load('display_names.json'), AREA_DATA: load('area_data.json'),
  REGIONS: load('regions_data.json'),
  GREAT_PROJECTS: (() => { try { return load('great_projects.json'); } catch { return {}; } })(),
});
for (const k of Object.keys(sb)) {
  try { vm.runInContext(`${k} = globalThis.${k}`, sb); } catch {}
}

const strip = s => String(s).replace(/<[^>]*>/g, '').replace(/&[a-z]+;/g, ' ').trim();
const ids = Object.keys(sb.TRIGGERS);
const out = [];
for (let tries = 0; tries < 500 && out.length < 12; tries++) {
  const id = ids[Math.floor(Math.random() * ids.length)];
  const m = sb.TRIGGERS[id];
  if (!m || !m.trigger_raw) continue;
  let lines = [];
  try {
    lines = (sb.parseTriggerToReadable(m.trigger_raw) || [])
      .map(l => strip(l.text || l)).filter(Boolean).slice(0, 3);
  } catch { continue; }
  if (!lines.length) continue;
  out.push(`- ${id}\n    ${lines.join('\n    ')}`);
}
console.log(out.join('\n'));
