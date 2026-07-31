/**
 * Headless audit of mission requirement/effect text quality.
 *
 * Loads index.html's renderer into a sandbox with the real data, renders every
 * mission's triggers and effects, and reports lines that still read as raw EU4
 * script rather than English. Run: node audit_text_quality.js [--samples N]
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const dir = __dirname;
const html = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
const load = f => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));

// Pull the inline <script> that holds the renderer
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const code = scripts.sort((a, b) => b.length - a.length)[0];

const stubEl = () => new Proxy(function () {}, {
  get: (t, p) => {
    if (p === 'style' || p === 'classList' || p === 'dataset') return stubEl();
    if (p === 'textContent' || p === 'innerHTML' || p === 'value') return '';
    if (p === Symbol.toPrimitive || p === 'toString') return () => '';
    return stubEl();
  },
  set: () => true,
  apply: () => stubEl(),
});

const sandbox = {
  console,
  document: {
    body: stubEl(),
    head: stubEl(),
    documentElement: stubEl(),
    getElementById: () => stubEl(),
    querySelector: () => stubEl(),
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => stubEl(),
  },
  window: { addEventListener: () => {}, matchMedia: () => ({ matches: false }) },
  localStorage: { getItem: () => null, setItem: () => {} },
  fetch: () => Promise.reject(new Error('no network in audit')),
  setTimeout, clearTimeout, Image: function () {},
};
sandbox.window.document = sandbox.document;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { filename: 'index-inline.js' });

// Inject real data
Object.assign(sandbox, {
  DATA: load('anbennar_data.json'),
  TRIGGERS: load('mission_triggers.json'),
  PROVINCES: load('province_names.json'),
  MODIFIERS: load('modifiers_data.json'),
  EVENT_NAMES: load('event_names.json'),
  SCRIPTED: load('scripted_defs.json'),
  NAMES: load('display_names.json'),
  GREAT_PROJECTS: (() => { try { return load('great_projects.json'); } catch { return {}; } })(),
  AREA_DATA: load('area_data.json'),
  REGIONS: load('regions_data.json'),
});
for (const k of Object.keys(sandbox)) {
  try { vm.runInContext(`${k} = globalThis.${k}`, sandbox); } catch {}
}

const strip = s => String(s).replace(/<[^>]*>/g, '').replace(/&[a-z]+;/g, ' ').trim();

// A line still reads as script if it carries snake_case tokens or bare `key = value`
const SCRIPTY = /(^|\s)[a-z][a-z0-9]*(_[a-z0-9]+){1,}(\s|:|$)/;

const missions = sandbox.TRIGGERS;
let total = 0, scripty = 0;
const offenders = new Map();

for (const [id, m] of Object.entries(missions)) {
  if (!m || typeof m !== 'object') continue;
  for (const field of ['trigger_raw', 'effect_raw']) {
    const raw = m[field];
    if (!raw) continue;
    let lines = [];
    try {
      lines = sandbox.parseTriggerToReadable
        ? sandbox.parseTriggerToReadable(raw)
        : [];
    } catch (e) { continue; }
    for (const ln of lines) {
      const text = strip(typeof ln === 'string' ? ln : (ln && ln.text) || '');
      if (!text) continue;
      total++;
      if (SCRIPTY.test(text)) {
        scripty++;
        const key = text.slice(0, 70);
        offenders.set(key, (offenders.get(key) || 0) + 1);
      }
    }
  }
}

console.log(`Rendered lines: ${total.toLocaleString()}`);
console.log(`Still script-like: ${scripty.toLocaleString()} (${(100 * scripty / Math.max(total, 1)).toFixed(1)}%)\n`);
const n = Number((process.argv.find(a => a.startsWith('--samples')) || '').split('=')[1] || 30);
console.log(`Top ${n} offending lines:`);
[...offenders.entries()].sort((a, b) => b[1] - a[1]).slice(0, n)
  .forEach(([t, c]) => console.log(`  ${String(c).padStart(5)}  ${t}`));

// --- harness self-check (temporary) ---
console.log('\n[selfcheck] renderer sees NAMES entries:',
  vm.runInContext('Object.keys(NAMES).length', sandbox));
console.log('[selfcheck] renderer sees SCRIPTED entries:',
  vm.runInContext('Object.keys(SCRIPTED).length', sandbox));
console.log('[selfcheck] dn("mage_tower") =',
  vm.runInContext('dn("mage_tower")', sandbox));
