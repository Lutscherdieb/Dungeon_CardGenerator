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
  profiles: {},     // type (lowercase) -> print profile
  icons: new Set(), // asset stems that exist, from /api/meta/icons
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

/** A version token that changes only when the render did.
 *
 * This used to be Date.now(), which made every grid repaint a fresh URL for
 * all 137 thumbnails -- so the browser re-downloaded the whole gallery any
 * time anything redrew it. Keying on the render timestamp means a repaint
 * reuses the cached images and only a genuinely re-rendered card refetches.
 */
function imageVersion(view) {
  return encodeURIComponent(view.render?.at || view.updated_at || '0');
}

/* ---------- grid ---------- */

/** Grid uses the small thumbnail; the detail panel uses the full trim image. */
function imageUrl(view, size = 'thumb') {
  if (view.render?.status === 'done' && view.render?.urls) {
    const url = view.render.urls[size] || view.render.urls.trim;
    return `${url}?v=${imageVersion(view)}`;
  }
  // Not rendered yet: show the artwork the card owns. There is no path to fall
  // back to any more -- the image lives in the store.
  return view.artwork?.url || null;
}

function buildTile(view) {
  const url = imageUrl(view, 'thumb');
  const img = el('img', { alt: view.name, loading: 'lazy' });
  if (url) img.src = url; else img.style.background = '#000';
  img.addEventListener('error', () => {
    const fallback = view.artwork?.url;
    if (fallback && !img.src.includes('/artwork')) img.src = fallback;
  });

  const status = view.render?.queue || view.render?.status || 'pending';
  const selected = state.current?.id === view.id ? ' selected' : '';
  return el('article', {
    class: `card${selected}`, tabindex: '0', role: 'button', 'data-id': view.id,
    onclick: () => openCard(view.id),
    onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCard(view.id); } },
  },
    img,
    el('span', { class: `dot ${status}`, title: `render: ${status}` }),
    el('div', { class: 'meta' },
      el('strong', { text: view.name }),
      el('span', { text: view.subtype ? `${view.type} · ${view.subtype}` : view.type })),
  );
}

function renderGrid() {
  const grid = $('#grid');
  grid.replaceChildren();
  const filter = $('#filter-type').value;
  const shown = state.cards.filter((c) => !filter || c.type === filter);

  if (!shown.length) {
    grid.append(el('p', { class: 'hint', text: 'No cards. Use "New card", or run: python -m cardgen.cli import' }));
    return;
  }
  for (const view of shown) grid.append(buildTile(view));
}

/** Refetch ONE card and swap just its tile. Selecting a card must never
 *  redraw the other 136 -- that is what made the whole gallery flicker. */
async function refreshCard(id) {
  const view = await getJSON(`/api/cards/${id}`).catch(() => null);
  if (!view) return;
  const i = state.cards.findIndex((c) => c.id === id);
  if (i >= 0) state.cards[i] = view; else state.cards.push(view);

  const tile = $(`#grid [data-id="${id}"]`);
  if (tile) tile.replaceWith(buildTile(view));

  if (state.current?.id === id) {
    state.current = view;
    $('#panel-title').textContent = `#${view.id} — ${view.name}`;
    paintRenderState(view);
  }
}

/* ---------- form builder ---------- */

function setDraft(key, value) { state.draft[key] = value; }

/** The icon a name prints on the card, or null.
 *
 * Derived, not listed: the templates resolve every icon as
 * `assets/<name lowercased>.png` (`assets/defence.png`, `assets/{{ Faction|lower }}.png`),
 * and /api/meta/icons says which of those files exist. So a field, an enum
 * value or a creature type shows its real printed icon, and a PNG dropped into
 * assets/ starts appearing here with no edit to this file.
 */
function iconFor(name) {
  const stem = String(name ?? '').toLowerCase();
  if (!state.icons.has(stem)) return null;
  return el('img', { class: 'icon', src: `/assets/${stem}.png`, alt: '', 'aria-hidden': 'true' });
}

/** Fill an icon slot with the first of `names` that has one. A field is tried
 *  by its key first (Mana -> mana.png), then by its value, which is what gives
 *  Faction=Demon the demon icon and Type=Spell the spell icon. */
function paintIcon(slot, ...names) {
  for (const name of names) {
    const img = iconFor(name);
    if (img) { slot.replaceChildren(img); return; }
  }
  slot.replaceChildren();
}

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

async function profileFor(type) {
  const key = String(type || '').toLowerCase();
  if (!state.profiles[key]) state.profiles[key] = await getJSON(`/api/meta/profile?card_type=${key}`);
  return state.profiles[key];
}

async function schemaFor(type) {
  const key = String(type || '').toLowerCase();
  if (!state.schemas[key]) state.schemas[key] = await getJSON(`/api/meta/schema?card_type=${key}`);
  return state.schemas[key];
}

/** Human file size. A 23KB upload reading "0.0 MB" is not a size. */
function fileSize(bytes) {
  if (!bytes && bytes !== 0) return '?';
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

/** What artwork the card currently holds, and what it should be. */
function paintArtwork(view, profile) {
  const art = view.artwork || {};
  const img = $('#art-current');
  if (art.present) {
    img.src = art.url;
    img.hidden = false;
    $('#art-meta').textContent =
      `${art.width}×${art.height} · ${art.mime?.replace('image/', '') || '?'} · ${fileSize(art.bytes)}`;
  } else {
    img.hidden = true;
    $('#art-meta').textContent = 'no artwork yet';
  }
  $('#art-hint').textContent =
    `Stored with the card. Fills the safe zone at ${profile.artwork_min[0]}×`
    + `${profile.artwork_min[1]}px; smaller still works, you just get a warning. `
    + 'Uploading replaces what is there.';
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
  const url = imageUrl(view, 'trim');
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

  paintArtwork(view, await profileFor(view.type));

  openPanel();
  markSelected(view.id);
  pollIfBusy(view);
}

function markSelected(id) {
  for (const tile of document.querySelectorAll('#grid .card.selected')) {
    tile.classList.remove('selected');
  }
  if (id !== null) $(`#grid [data-id="${id}"]`)?.classList.add('selected');
}

function openPanel() {
  $('#panel').classList.add('open');
  $('#panel').setAttribute('aria-hidden', 'false');
  document.body.classList.add('panel-open');
}

function closePanel() {
  stopPolling();
  markSelected(null);
  state.current = null;
  state.draft = null;
  $('#panel').classList.remove('open');
  $('#panel').setAttribute('aria-hidden', 'true');
  document.body.classList.remove('panel-open');
}

/** Start polling only if this card has work in flight.
 *
 * Polling used to start on every open, so 1.2s after selecting any card the
 * first tick found it idle and triggered a full gallery reload.
 */
function pollIfBusy(view) {
  const status = view.render?.queue || view.render?.status;
  if (status === 'queued' || status === 'rendering') startPolling(view.id);
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
    if (!busy) { stopPolling(); await refreshCard(id); }
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
  await refreshCard(id);
  startPolling(id);
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

    // Artwork is a property of the card in the store, so nothing in the form
    // refers to it and a later save cannot revert it. Just repaint the preview.
    state.current.artwork = { ...res.artwork, present: true };
    state.current.artwork.url =
      `/api/cards/${state.current.id}/artwork?v=${res.artwork.width}x${res.artwork.height}-${res.artwork.bytes}`;
    paintArtwork(state.current, await profileFor(state.current.type));

    banner('');
    input.value = '';
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

  try {
    const { id } = await sendJSON('/api/cards', 'POST', card);
    await reload();
    await openCard(id);
    banner('Created. Upload artwork for it — it will render on a black background until you do.', 'warn');
  } catch (err) {
    banner(String(err.message || err), 'error');
  }
}

/* ---------- boot ---------- */

/** The asset stems, fetched once. A form built before this lands would simply
 *  show no icons, so it is awaited ahead of the first paint rather than guarded
 *  for at every call site. */
async function loadIcons() {
  const { icons } = await getJSON('/api/meta/icons').catch(() => ({ icons: [] }));
  state.icons = new Set(icons);
}

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
  $('#btn-save').addEventListener('click', save);
  $('#btn-render').addEventListener('click', rerender);
  $('#btn-delete').addEventListener('click', removeCard);
  $('#btn-art').addEventListener('click', uploadArtwork);
  $('#filter-type').addEventListener('change', renderGrid);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePanel(); });
}

wire();
loadIcons()
  .then(() => reload())
  .catch((err) => banner(String(err.message || err), 'error'));
