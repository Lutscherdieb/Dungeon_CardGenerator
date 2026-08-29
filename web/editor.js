/* The card editor: preview, artwork, the data form, and the actions.
 *
 * It owns `state.current` and `state.draft`, and it is the only module that
 * writes cards back to the server.
 */

import { api, getJSON, sendJSON } from './api.js';
import { loadAll, refreshCard } from './cards.js';
import { $, banner, fileSize } from './dom.js';
import { markSelected } from './grid.js';
import { buildForm } from './form.js';
import { isBusy, paintRenderState, startPolling, stopPolling } from './render.js';
import { blankCard, profileFor, schemaFor } from './schema.js';
import { state } from './state.js';

/* ---------- artwork ---------- */

/** What artwork the card currently holds, and what it should be. */
async function paintArtwork(view) {
  const profile = await profileFor(view.type);
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

/* ---------- open / close ---------- */

export async function openCard(id) {
  const view = await getJSON(`/api/cards/${id}`);
  state.current = view;
  state.draft = structuredClone(view.card);

  $('#panel-title').textContent = `#${view.id} — ${view.name}`;
  $('#form-error').hidden = true;
  $('#art-warning').hidden = true;
  paintRenderState(view);
  buildForm($('#form-fields'), await schemaFor(view.type));
  await paintArtwork(view);

  $('#panel').classList.add('open');
  $('#panel').setAttribute('aria-hidden', 'false');
  document.body.classList.add('panel-open');

  markSelected(view.id);
  if (isBusy(view)) poll(view.id);
}

export function closePanel() {
  stopPolling();
  markSelected(null);
  state.current = null;
  state.draft = null;
  $('#panel').classList.remove('open');
  $('#panel').setAttribute('aria-hidden', 'true');
  document.body.classList.remove('panel-open');
}

/* ---------- polling ---------- */

function poll(id) {
  startPolling(id, {
    isCurrent: (cid) => state.current?.id === cid,
    onTick: (status) => {
      state.current.render = { ...state.current.render, ...status };
      paintRenderState(state.current);
    },
    onSettled: async (cid) => {
      const view = await refreshCard(cid);
      if (view && state.current?.id === cid) {
        state.current = view;
        $('#panel-title').textContent = `#${view.id} — ${view.name}`;
        paintRenderState(view);
      }
    },
  });
}

/* ---------- actions ---------- */

export async function save() {
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
  const view = await refreshCard(id);
  if (view && state.current?.id === id) {
    state.current = view;
    $('#panel-title').textContent = `#${view.id} — ${view.name}`;
    paintRenderState(view);
  }
  poll(id);
}

export async function uploadArtwork() {
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
    await paintArtwork(state.current);

    banner('');
    input.value = '';
    poll(state.current.id);
  } catch (err) {
    banner(String(err.message || err), 'error');
  }
}

export async function rerender() {
  if (!state.current) return;
  await sendJSON(`/api/cards/${state.current.id}/render`, 'POST', {});
  poll(state.current.id);
}

export async function removeCard() {
  if (!state.current) return;
  if (!confirm(`Delete "${state.current.name}"? The card row goes; the artwork file stays.`)) return;
  await api(`/api/cards/${state.current.id}`, { method: 'DELETE' });
  closePanel();
  await loadAll();
}

export async function newCard() {
  const { types } = await getJSON('/api/meta/types');
  const type = prompt(`Card type?\n\n${types.join(', ')}`, types[0]);
  if (!type) return;
  const key = type.trim().toLowerCase();
  let schema;
  try { schema = await schemaFor(key); }
  catch { banner(`Unknown card type "${type}".`, 'error'); return; }

  const card = blankCard(schema);
  card.Name = 'Untitled';

  try {
    const { id } = await sendJSON('/api/cards', 'POST', card);
    closePanel();
    await loadAll();
    await openCard(id);
    banner('Created. Upload artwork for it — it will render on a black background until you do.', 'warn');
  } catch (err) {
    banner(String(err.message || err), 'error');
  }
}
