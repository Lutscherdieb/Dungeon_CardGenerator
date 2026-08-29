/* CardGenerator gallery — boot and wiring.
 *
 * This file holds no behaviour of its own. It loads the icon set, fetches the
 * deck, and connects the page's controls to the modules that do the work:
 *
 *   api.js      the fetch layer
 *   dom.js      $, el(), banner(), fileSize()
 *   state.js    the shared card cache and the open card
 *   schema.js   per-type JSON Schemas and print profiles
 *   icons.js    which assets/*.png exist, and the <img> for one
 *   cards.js    loading the deck, refreshing one card
 *   grid.js     the tiles and which is selected
 *   form.js     the schema-driven card-data form
 *   render.js   render status and polling
 *   editor.js   the open card: preview, artwork, form, actions
 */

import { loadAll } from './cards.js';
import { $, banner, el } from './dom.js';
import {
  closePanel, newCard, openCard, removeCard, rerender, save, uploadArtwork,
} from './editor.js';
import { renderGrid, setFilter } from './grid.js';
import { loadIcons } from './icons.js';

/** Rebuild the topbar type filter from the types actually in the deck. */
function refreshTypeOptions(cards) {
  const filter = $('#filter-type');
  const chosen = filter.value;
  const types = [...new Set(cards.map((c) => c.type))].sort();
  filter.replaceChildren(el('option', { value: '', text: 'all' }),
    ...types.map((t) => el('option', { value: t, text: t })));
  filter.value = chosen;
}

function wire() {
  document.addEventListener('cards:loaded', (e) => refreshTypeOptions(e.detail.cards));
  $('#grid').addEventListener('card:select', (e) => openCard(e.detail.id));

  $('#btn-refresh').addEventListener('click', () => { closePanel(); loadAll(); });
  $('#btn-new').addEventListener('click', newCard);
  $('#btn-close').addEventListener('click', closePanel);
  $('#btn-save').addEventListener('click', save);
  $('#btn-render').addEventListener('click', rerender);
  $('#btn-delete').addEventListener('click', removeCard);
  $('#btn-art').addEventListener('click', uploadArtwork);

  const typeFilter = $('#filter-type');
  setFilter((card) => !typeFilter.value || card.type === typeFilter.value);
  typeFilter.addEventListener('change', renderGrid);

  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePanel(); });
}

wire();
loadIcons()
  .then(() => loadAll())
  .catch((err) => banner(String(err.message || err), 'error'));
