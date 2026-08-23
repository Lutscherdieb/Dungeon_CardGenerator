/* CardGenerator gallery.
 *
 * The edit form is built from the card type's JSON Schema, which is generated
 * from the pydantic model -- so adding a field to the model makes it appear
 * here with no change to this file. Anything whose shape this builder does not
 * recognise falls back to a JSON text box rather than silently dropping out of
 * the form; a field you cannot see is a field you cannot fix.
 */

const $ = (sel) => document.querySelector(sel);

const state = {
  cards: [],
  schemas: {},      // type (lowercase) -> schema
  current: null,    // the open card view
  draft: null,      // edited copy of current.card
  poll: null,
};

/* ---------- api ---------- */

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const text = await res.text();
  let body = null;
  if (text) {
    try { body = JSON.parse(text); }
    catch { throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`); }
  }
  if (!res.ok) throw new Error(body?.error || `${res.status} ${res.statusText}`);
  return body;
}

const getJSON = (p) => api(p);
const sendJSON = (p, method, payload) => api(p, {
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

/* ---------- helpers ---------- */

function banner(message, tone = 'warn') {
  const el = $('#banner');
  if (!message) { el.hidden = true; return; }
  el.hidden = false;
  el.textContent = message;
  el.style.color = tone === 'error' ? 'var(--danger)' : 'var(--warn)';
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c) node.append(c);
  return node;
}

/** Resolve a local $ref against the schema's own $defs. */
function deref(schema, node) {
  if (!node || !node.$ref) return node;
  const name = node.$ref.replace('#/$defs/', '');
  return schema.$defs?.[name] || node;
}

function cacheBust(url) { return `${url}?t=${Date.now()}`; }

/* ---------- grid ---------- */

function thumbUrl(view) {
  if (view.render?.status === 'done' && view.render?.urls) return cacheBust(view.render.urls.trim);
  const bg = view.card?.Background;
  if (bg) return bg.replace(/^\.\//, '/');
  return null;
}

function renderGrid() {
  const grid = $('#grid');
  grid.replaceChildren();
  const filter = $('#filter-type').value;
  const shown = state.cards.filter((c) => !filter || c.type === filter);

  if (!shown.length) {
    grid.append(el('p', { class: 'hint', text: 'No cards. Use "New card", or run: cardgen import' }));
    return;
  }

  for (const view of shown) {
    const url = thumbUrl(view);
    const img = el('img', { alt: view.name, loading: 'lazy' });
    if (url) img.src = url; else img.style.background = '#000';
    img.addEventListener('error', () => {
      const bg = view.card?.Background;
      const fallback = bg ? bg.replace(/^\.\//, '/') : null;
      if (fallback && !img.src.includes(fallback)) img.src = fallback;
    });

    const status = view.render?.queue || view.render?.status || 'pending';
    grid.append(el('article', {
      class: 'card', tabindex: '0', role: 'button',
      onclick: () => openCard(view.id),
      onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCard(view.id); } },
    },
      img,
      el('span', { class: `dot ${status}`, title: `render: ${status}` }),
      el('div', { class: 'meta' },
        el('strong', { text: view.name }),
        el('span', { text: view.subtype ? `${view.type} · ${view.subtype}` : view.type })),
    ));
  }
}

/* ---------- form builder ---------- */

function setDraft(key, value) { state.draft[key] = value; }

function fieldWrap(label, control, hint) {
  return el('label', { class: 'field' },
    el('span', { text: label }), control,
    hint ? el('span', { class: 'hint', text: hint }) : null);
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
      wrap.append(el('span', { class: 'tag' }, el('span', { text: v }),
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
        group.append(el('div', { class: 'spot' },
          buildEnumSelect(creatureTypes, spot[0], (v) => { spot[0] = v; }),
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
  return fieldWrap('Slots', wrap, 'Creature spots per group. The number is a badge on the card; what it means is still open.');
}

function buildField(schema, key, spec) {
  const value = state.draft[key];
  const resolved = deref(schema, spec);

  if (spec.const !== undefined) {
    return fieldWrap(key, el('input', { type: 'text', value: spec.const, readonly: 'readonly' }));
  }

  if (resolved.enum) {
    return fieldWrap(key, buildEnumSelect(resolved.enum, value, (v) => setDraft(key, v)));
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
    return fieldWrap(key, control, long ? 'Use [Mana], [Demon], [Wild] … for inline icons.' : null);
  }

  if (resolved.type === 'array') {
    const items = deref(schema, resolved.items);
    if (items?.enum) {
      return fieldWrap(key, buildTagList(key, value, items.enum));
    }
    if (items?.type === 'array' && items.prefixItems) {
      const first = deref(schema, items.prefixItems[0]);
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
  return fieldWrap(key, box, 'No editor for this shape yet — raw JSON.');
}

function buildForm(schema) {
  const host = $('#form-fields');
  host.replaceChildren();
  const order = schema['x-key-order'] || Object.keys(schema.properties || {});
  for (const key of order) {
    const spec = schema.properties?.[key];
    if (spec) host.append(buildField(schema, key, spec));
  }
}

/* ---------- panel ---------- */

async function schemaFor(type) {
  const key = String(type || '').toLowerCase();
  if (!state.schemas[key]) state.schemas[key] = await getJSON(`/api/meta/schema?card_type=${key}`);
  return state.schemas[key];
}

function paintRenderState(view) {
  const status = view.render?.queue || view.render?.status || 'pending';
  const node = $('#render-state');
  node.className = `render-state ${status}`;
  node.textContent = view.render?.error
    ? `render failed — ${view.render.error}`
    : `render: ${status}`;

  const urls = view.render?.urls || {};
  $('#link-canvas').href = urls.canvas || '#';
  $('#link-trim').href = urls.trim || '#';
  $('#link-safe').href = urls.safe || '#';

  const img = $('#preview-img');
  const url = thumbUrl(view);
  if (url) img.src = url;
}

async function openCard(id) {
  const view = await getJSON(`/api/cards/${id}`);
  state.current = view;
  state.draft = structuredClone(view.card);

  $('#panel-title').textContent = `#${view.id} — ${view.name}`;
  $('#form-error').hidden = true;
  $('#art-warning').hidden = true;
  paintRenderState(view);
  buildForm(await schemaFor(view.type));

  const profile = await getJSON(`/api/meta/profile?card_type=${view.type}`);
  $('#art-hint').textContent =
    `Fills the safe zone at ${profile.artwork_min[0]}×${profile.artwork_min[1]}px. `
    + 'Smaller art still works — you just get a warning that it will print soft.';

  $('#panel').hidden = false;
  $('#scrim').hidden = false;
  startPolling(id);
}

function closePanel() {
  stopPolling();
  state.current = null;
  state.draft = null;
  $('#panel').hidden = true;
  $('#scrim').hidden = true;
}

function startPolling(id) {
  stopPolling();
  state.poll = setInterval(async () => {
    if (!state.current || state.current.id !== id) return stopPolling();
    const view = await getJSON(`/api/cards/${id}/render`).catch(() => null);
    if (!view) return;
    const busy = view.queue === 'queued' || view.queue === 'rendering';
    state.current.render = { ...state.current.render, ...view };
    paintRenderState(state.current);
    if (!busy) { stopPolling(); await reload({ keepPanel: true }); }
  }, 1200);
}

function stopPolling() {
  if (state.poll) { clearInterval(state.poll); state.poll = null; }
}

/* ---------- actions ---------- */

async function save() {
  if (!state.current) return;
  const id = state.current.id;
  $('#form-error').hidden = true;
  try {
    await sendJSON(`/api/cards/${id}`, 'PUT', { card: state.draft });
  } catch (err) {
    const node = $('#form-error');
    node.hidden = false;
    node.textContent = String(err.message || err);
    return;
  }
  const view = await getJSON(`/api/cards/${id}`);
  state.current = view;
  $('#panel-title').textContent = `#${view.id} — ${view.name}`;
  paintRenderState(view);
  startPolling(id);
  await reload({ keepPanel: true });
}

async function uploadArtwork() {
  if (!state.current) return;
  const input = $('#art-file');
  if (!input.files?.length) { banner('Choose an image first.'); return; }
  const form = new FormData();
  form.append('file', input.files[0]);
  const warn = $('#art-warning');
  warn.hidden = true;
  try {
    const res = await api(`/api/cards/${state.current.id}/artwork`, { method: 'POST', body: form });
    if (res.warnings?.length) { warn.hidden = false; warn.textContent = res.warnings.join(' · '); }
    banner('');
    startPolling(state.current.id);
  } catch (err) {
    banner(String(err.message || err), 'error');
  }
}

async function rerender() {
  if (!state.current) return;
  await sendJSON(`/api/cards/${state.current.id}/render`, 'POST', {});
  startPolling(state.current.id);
}

async function removeCard() {
  if (!state.current) return;
  if (!confirm(`Delete "${state.current.name}"? The card row goes; the artwork file stays.`)) return;
  await api(`/api/cards/${state.current.id}`, { method: 'DELETE' });
  closePanel();
  await reload();
}

async function newCard() {
  const types = Object.keys(state.schemas).length
    ? Object.keys(state.schemas)
    : (await getJSON('/api/meta/types')).types;
  const type = prompt(`Card type?\n\n${types.join(', ')}`, types[0]);
  if (!type) return;
  const key = type.trim().toLowerCase();
  let schema;
  try { schema = await schemaFor(key); }
  catch { banner(`Unknown card type "${type}".`, 'error'); return; }

  const card = {};
  for (const [k, spec] of Object.entries(schema.properties || {})) {
    if (spec.const !== undefined) card[k] = spec.const;
    else if (spec.default !== undefined) card[k] = spec.default;
    else {
      const resolved = deref(schema, spec);
      if (resolved.enum) card[k] = resolved.enum[0];
      else if (resolved.type === 'integer') card[k] = resolved.minimum ?? 0;
      else if (resolved.type === 'array') card[k] = [];
      else card[k] = '';
    }
  }
  card.Name = 'Untitled';
  card.Background = './backgrounds/Untitled.png';

  try {
    const { id } = await sendJSON('/api/cards', 'POST', card);
    await reload();
    await openCard(id);
    banner('Created. It will fail to render until you upload artwork.', 'warn');
  } catch (err) {
    banner(String(err.message || err), 'error');
  }
}

/* ---------- boot ---------- */

async function reload({ keepPanel = false } = {}) {
  const { cards } = await getJSON('/api/cards');
  state.cards = cards;

  const filter = $('#filter-type');
  const chosen = filter.value;
  const types = [...new Set(cards.map((c) => c.type))].sort();
  filter.replaceChildren(el('option', { value: '', text: 'all' }),
    ...types.map((t) => el('option', { value: t, text: t })));
  filter.value = chosen;

  renderGrid();
  if (!keepPanel && state.current) closePanel();
}

function wire() {
  $('#btn-refresh').addEventListener('click', () => reload());
  $('#btn-new').addEventListener('click', newCard);
  $('#btn-close').addEventListener('click', closePanel);
  $('#scrim').addEventListener('click', closePanel);
  $('#btn-save').addEventListener('click', save);
  $('#btn-render').addEventListener('click', rerender);
  $('#btn-delete').addEventListener('click', removeCard);
  $('#btn-art').addEventListener('click', uploadArtwork);
  $('#filter-type').addEventListener('change', renderGrid);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePanel(); });
}

wire();
reload().catch((err) => banner(String(err.message || err), 'error'));
