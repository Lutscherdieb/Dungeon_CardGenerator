/* The filter panel: every card attribute, filterable, in one popover.
 *
 * The controls are DERIVED from the card schemas, never listed here. Each
 * property's JSON Schema shape picks its control:
 *
 *   const            -> chip set   (Type)
 *   enum             -> chip set   (Subtype, Faction)
 *   boolean          -> any/yes/no (Starter)
 *   integer          -> min-max    (Tier, Mana, Cards, Food, Defence, ...)
 *   string           -> contains   (Name, Description)
 *   array of enum    -> chip set, "has any of"  (Roads, Creatures, Slots)
 *
 * So a field added to cardgen.model appears here with no edit to this file --
 * the same property the form builder has. Two facets are NOT card fields and
 * are declared explicitly at the bottom: render status and whether artwork
 * has been uploaded.
 *
 * Filtering is client-side. GET /api/cards already returns every card's whole
 * JSON (137 of them), so there is nothing to ask the server for.
 */

import { el } from './dom.js';
import { renderGrid, setFilter } from './grid.js';
import { popover } from './popover.js';
import { allSchemas, deref } from './schema.js';

const STORAGE_KEY = 'cardgen.filters';

/** Facets that live on the row rather than in the card JSON. */
const EXTRA_FACETS = [
  {
    key: '_render',
    label: 'Render',
    kind: 'chips',
    options: ['pending', 'queued', 'rendering', 'done', 'error'],
    read: (view) => [view.render?.queue || view.render?.status || 'pending'],
  },
  {
    key: '_artwork',
    label: 'Artwork',
    kind: 'tri',
    read: (view) => Boolean(view.artwork?.present),
  },
];

/** The active filter values, by field key. Persisted across reloads. */
let values = load();

/** The field descriptors, built once from the schemas. */
let fields = [];

function load() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { return {}; }
}

function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(values)); } catch { /* private mode */ }
}

/* ---------- deriving the fields from the schemas ---------- */

/** One descriptor per filterable property, unioned across every card type. */
function describe(schemas) {
  const byKey = new Map();

  const add = (key, patch) => {
    const found = byKey.get(key) || { key, label: key, read: (v) => v.card?.[key] };
    byKey.set(key, { ...found, ...patch, options: mergeOptions(found.options, patch.options) });
  };

  for (const schema of Object.values(schemas)) {
    for (const [key, raw] of Object.entries(schema.properties || {})) {
      const spec = deref(schema, raw);

      if (raw.const !== undefined) { add(key, { kind: 'chips', options: [raw.const] }); continue; }
      if (spec.enum) { add(key, { kind: 'chips', options: spec.enum }); continue; }
      if (spec.type === 'boolean') { add(key, { kind: 'tri' }); continue; }
      if (spec.type === 'integer' || spec.type === 'number') { add(key, { kind: 'range' }); continue; }
      if (spec.type === 'string') { add(key, { kind: 'text' }); continue; }
      if (spec.type === 'array') {
        const items = deref(schema, spec.items);
        if (items?.enum) add(key, { kind: 'chips', options: items.enum, multi: true });
        continue;                 // any other array shape is not filterable
      }
    }
  }

  // Present them in the schemas' own key order, which is the order the form and
  // the exported JSON use, so the panel reads like the card.
  const order = [...new Set(Object.values(schemas).flatMap((s) => s['x-key-order'] || []))];
  const ranked = [...byKey.values()].sort(
    (a, b) => (order.indexOf(a.key) + 1 || 99) - (order.indexOf(b.key) + 1 || 99));
  return [...ranked, ...EXTRA_FACETS];
}

function mergeOptions(a, b) {
  if (!a && !b) return undefined;
  return [...new Set([...(a || []), ...(b || [])])];
}

/* ---------- the predicate ---------- */

function activeCount() {
  return fields.filter((f) => isActive(f, values[f.key])).length;
}

function isActive(field, value) {
  if (value === undefined || value === null) return false;
  if (field.kind === 'chips') return Array.isArray(value) && value.length > 0;
  if (field.kind === 'range') return value.min !== null || value.max !== null;
  if (field.kind === 'text') return String(value).trim() !== '';
  if (field.kind === 'tri') return typeof value === 'boolean';
  return false;
}

function matches(view) {
  for (const field of fields) {
    const wanted = values[field.key];
    if (!isActive(field, wanted)) continue;
    const actual = field.read(view);

    if (field.kind === 'chips') {
      const have = Array.isArray(actual) ? actual : [actual];
      if (!have.some((v) => wanted.includes(v))) return false;
    } else if (field.kind === 'range') {
      if (typeof actual !== 'number') return false;
      if (wanted.min !== null && actual < wanted.min) return false;
      if (wanted.max !== null && actual > wanted.max) return false;
    } else if (field.kind === 'text') {
      if (!String(actual ?? '').toLowerCase().includes(String(wanted).toLowerCase())) return false;
    } else if (field.kind === 'tri') {
      if (Boolean(actual) !== wanted) return false;
    }
  }
  return true;
}

/* ---------- the controls ---------- */

function set(key, value) {
  values[key] = value;
  save();
  renderGrid();
  paintCount();
}

function chipRow(field) {
  const chosen = () => values[field.key] || [];
  const wrap = el('div', { class: 'chips' });
  for (const option of field.options || []) {
    const chip = el('button', {
      type: 'button',
      class: `chip${chosen().includes(option) ? ' on' : ''}`,
      text: option,
      onclick: () => {
        const next = chosen().includes(option)
          ? chosen().filter((v) => v !== option)
          : [...chosen(), option];
        set(field.key, next);
        chip.classList.toggle('on', next.includes(option));
      },
    });
    wrap.append(chip);
  }
  return wrap;
}

function rangeRow(field) {
  const current = values[field.key] || { min: null, max: null };
  const num = (which) => el('input', {
    type: 'number', class: 'mini', placeholder: which, value: current[which] ?? '',
    oninput: (e) => {
      const next = { ...(values[field.key] || { min: null, max: null }) };
      next[which] = e.target.value === '' ? null : Number(e.target.value);
      set(field.key, next);
    },
  });
  return el('div', { class: 'range' }, num('min'), el('span', { text: '–' }), num('max'));
}

function textRow(field) {
  let pending = null;
  return el('input', {
    type: 'text', placeholder: 'contains…', value: values[field.key] || '',
    oninput: (e) => {
      // Debounced: `set` repaints all 137 tiles, and doing that per keystroke
      // is the kind of churn this gallery has been bitten by before.
      clearTimeout(pending);
      const text = e.target.value;
      pending = setTimeout(() => set(field.key, text), 150);
    },
  });
}

function triRow(field) {
  const wrap = el('div', { class: 'chips' });
  const choices = [['any', null], ['yes', true], ['no', false]];
  for (const [label, value] of choices) {
    wrap.append(el('button', {
      type: 'button',
      class: `chip${(values[field.key] ?? null) === value ? ' on' : ''}`,
      text: label,
      onclick: () => {
        set(field.key, value);
        for (const c of wrap.children) c.classList.remove('on');
        wrap.children[choices.findIndex(([, v]) => v === value)].classList.add('on');
      },
    }));
  }
  return wrap;
}

const CONTROLS = { chips: chipRow, range: rangeRow, text: textRow, tri: triRow };

function paintCount() {
  const n = activeCount();
  const button = document.getElementById('btn-filters');
  button.textContent = n ? `Filters (${n})` : 'Filters';
  button.classList.toggle('primary', n > 0);
}

/* ---------- setup ---------- */

export async function initFilters(button) {
  fields = describe(await allSchemas());
  setFilter(matches);

  const pop = popover(button, { title: 'Filters', width: 340 });
  pop.body.append(
    ...fields.map((field) => el('div', { class: 'filter-row' },
      el('span', { class: 'filter-label', text: field.label || field.key }),
      CONTROLS[field.kind](field))),
    el('div', { class: 'filter-foot' },
      el('button', {
        type: 'button', class: 'btn small', text: 'Clear all',
        onclick: () => { values = {}; save(); rebuild(pop); renderGrid(); paintCount(); },
      })),
  );

  paintCount();
  return pop;
}

/** Redraw every control from `values`. Only needed by "Clear all". */
function rebuild(pop) {
  const rows = [...pop.body.querySelectorAll('.filter-row')];
  rows.forEach((row, i) => {
    const field = fields[i];
    row.lastElementChild.replaceWith(CONTROLS[field.kind](field));
  });
}
