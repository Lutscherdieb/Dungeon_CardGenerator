/* The card-data form, built from the card type's JSON Schema.
 *
 * The schema is generated from the pydantic model, so adding a field to the
 * model makes it appear here with no change to this file. Anything whose shape
 * this builder does not recognise falls back to a JSON text box rather than
 * silently dropping out of the form; a field you cannot see is a field you
 * cannot fix.
 *
 * That fallback is silent by design, which is exactly why nothing reported that
 * `Slots` had been landing in it for the life of the feature. It is guarded now:
 * tests/check_gallery.py opens one card of every type and fails if any field
 * reaches the fallback.
 */

import { el } from './dom.js';
import { iconFor, paintIcon } from './icons.js';
import { deref } from './schema.js';
import { state } from './state.js';

function setDraft(key, value) { state.draft[key] = value; }

/** One form row: [icon] label | control, on a single line.
 *
 * The label used to sit above the control and every explanation printed a third
 * line below it, so eight fields filled the panel twice over. The explanation is
 * the row's tooltip now; `data-hint` marks the labels that carry one so a hint
 * that is invisible is still discoverable.
 */
function fieldWrap(label, control, hint, { tall = false } = {}) {
  const slot = el('span', { class: 'field-icon' });
  paintIcon(slot, label);
  return el('label', {
    class: `field${tall ? ' tall' : ''}`,
    'data-key': label,
    'data-hint': hint ? '' : null,
    title: hint || null,
  },
    el('span', { class: 'field-label' }, slot, el('span', { text: label })),
    control);
}

function buildEnumSelect(values, current, onChange, { allowBlank = false } = {}) {
  const sel = el('select', { onchange: (e) => onChange(e.target.value || null) });
  if (allowBlank) sel.append(el('option', { value: '', text: '—' }));
  for (const v of values) {
    const opt = el('option', { value: v, text: v });
    if (v === current) opt.selected = true;
    sel.append(opt);
  }
  return sel;
}

function buildTagList(key, values, options) {
  const wrap = el('div', { class: 'tags' });
  const redraw = () => {
    wrap.replaceChildren();
    (state.draft[key] || []).forEach((v, i) => {
      wrap.append(el('span', { class: 'tag' }, iconFor(v), el('span', { text: v }),
        el('button', {
          type: 'button', title: 'remove', text: '×',
          onclick: () => { state.draft[key].splice(i, 1); redraw(); },
        })));
    });
    const adder = el('select', {
      onchange: (e) => {
        if (!e.target.value) return;
        state.draft[key] = [...(state.draft[key] || []), e.target.value];
        redraw();
      },
    }, el('option', { value: '', text: '+ add' }), ...options.map((o) => el('option', { value: o, text: o })));
    wrap.append(adder);
  };
  redraw();
  return wrap;
}

function buildSlots(key, creatureTypes) {
  const wrap = el('div');
  const redraw = () => {
    wrap.replaceChildren();
    const groups = state.draft[key] || [];
    groups.forEach((spots, gi) => {
      const group = el('div', { class: 'slot-group' },
        el('header', {},
          el('span', { text: `Group ${gi + 1}` }),
          el('span', { class: 'spacer', style: 'flex:1' }),
          el('button', {
            type: 'button', class: 'btn small', text: '+ spot',
            onclick: () => { spots.push(['All', 0]); redraw(); },
          }),
          el('button', {
            type: 'button', class: 'btn small danger', text: 'remove group',
            onclick: () => { groups.splice(gi, 1); redraw(); },
          })));

      spots.forEach((spot, si) => {
        const slot = el('span', { class: 'field-icon' });
        paintIcon(slot, spot[0]);
        group.append(el('div', { class: 'spot' },
          slot,
          buildEnumSelect(creatureTypes, spot[0], (v) => { spot[0] = v; paintIcon(slot, v); }),
          el('input', {
            type: 'number', value: spot[1], title: 'the second number — meaning not yet decided',
            oninput: (e) => { spot[1] = Number(e.target.value || 0); },
          }),
          el('button', {
            type: 'button', class: 'btn small', text: '×',
            onclick: () => { spots.splice(si, 1); redraw(); },
          })));
      });
      wrap.append(group);
    });
    wrap.append(el('button', {
      type: 'button', class: 'btn small', text: '+ group',
      onclick: () => { state.draft[key] = [...groups, []]; redraw(); },
    }));
  };
  redraw();
  return fieldWrap('Slots', wrap,
    'Creature spots per group. The number is a badge on the card; what it means is still open.',
    { tall: true });
}

function buildField(schema, key, spec) {
  const value = state.draft[key];
  const resolved = deref(schema, spec);

  // A field's own icon wins; failing that, the icon of its value -- which is what
  // gives Type and Faction the icon they actually stamp on the card. The two
  // branches below are the ones whose value can have one.
  if (spec.const !== undefined) {
    const row = fieldWrap(key, el('input', { type: 'text', value: spec.const, readonly: 'readonly' }));
    paintIcon(row.querySelector('.field-icon'), key, spec.const);
    return row;
  }

  if (resolved.enum) {
    const row = fieldWrap(key, null);
    const slot = row.querySelector('.field-icon');
    const repaint = (v) => paintIcon(slot, key, v);
    row.append(buildEnumSelect(resolved.enum, value, (v) => { setDraft(key, v); repaint(v); }));
    repaint(value);
    return row;
  }

  if (resolved.type === 'integer' || resolved.type === 'number') {
    const control = el('input', {
      type: 'number', value: value ?? 0,
      min: resolved.minimum, max: resolved.maximum,
      oninput: (e) => setDraft(key, e.target.value === '' ? null : Number(e.target.value)),
    });
    return fieldWrap(key, control);
  }

  if (resolved.type === 'string') {
    const long = key === 'Description';
    const control = el(long ? 'textarea' : 'input', {
      type: long ? null : 'text',
      oninput: (e) => setDraft(key, e.target.value),
    });
    control.value = value ?? '';
    return fieldWrap(key, control,
      long ? 'Use [Mana], [Demon], [Wild] … for inline icons.' : null,
      { tall: long });
  }

  if (resolved.type === 'array') {
    const items = deref(schema, resolved.items);
    if (items?.enum) {
      return fieldWrap(key, buildTagList(key, value, items.enum), null, { tall: true });
    }
    // Slots is List[List[SlotSpot]] -- groups of spots -- so the pair shape sits
    // two levels down. Testing only one level left buildSlots unreachable and
    // dropped every Room's Slots into the raw-JSON fallback instead.
    if (items?.type === 'array') {
      const pair = deref(schema, items.prefixItems ? items : items.items);
      const first = deref(schema, pair?.prefixItems?.[0]);
      if (first?.enum) return buildSlots(key, first.enum);
    }
  }

  // Unrecognised shape: show it as JSON rather than hiding it.
  const box = el('textarea', {
    oninput: (e) => {
      try { setDraft(key, JSON.parse(e.target.value)); e.target.setCustomValidity(''); }
      catch { e.target.setCustomValidity('not valid JSON'); }
    },
  });
  box.value = JSON.stringify(value ?? null, null, 2);
  return fieldWrap(key, box, 'No editor for this shape yet — raw JSON.', { tall: true });
}

/** Fill `host` with one row per property, in the schema's own key order. */
export function buildForm(host, schema) {
  host.replaceChildren();
  const order = schema['x-key-order'] || Object.keys(schema.properties || {});
  for (const key of order) {
    const spec = schema.properties?.[key];
    if (spec) host.append(buildField(schema, key, spec));
  }
}
