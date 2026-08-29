/* CardGenerator gallery — boot and wiring.
 *
 * This file holds no behaviour of its own. It loads the icon set, fetches the
 * deck, and connects the page's controls to the modules that do the work:
 *
 *   api.js       the fetch layer
 *   dom.js       $, el(), banner(), fileSize()
 *   state.js     the shared card cache and the open card
 *   schema.js    per-type JSON Schemas, print profiles, blank cards
 *   icons.js     which assets/*.png exist, and the <img> for one
 *   cards.js     loading the deck, refreshing one card
 *   grid.js      the tiles, the selection, and where the inline editor sits
 *   form.js      the schema-driven card-data form
 *   codes.js     the [] icon-code legend under the Description field
 *   render.js    render status and polling
 *   editor.js    the open card: preview, artwork, form, actions
 *   popover.js   the floating-panel chrome shared by the two below
 *   filters.js   the filter panel, derived from the schemas
 *   newcard.js   the New card dialog
 */

import { loadAll } from './cards.js';
import { loadCodes } from './codes.js';
import { $, banner } from './dom.js';
import {
  closePanel, newCard, openCard, removeCard, rerender, save, uploadArtwork,
} from './editor.js';
import { initFilters } from './filters.js';
import { watchResize } from './grid.js';
import { loadIcons } from './icons.js';
import { initNewCard } from './newcard.js';
import { closeAllPopovers } from './popover.js';

function wire() {
  $('#grid').addEventListener('card:select', (e) => openCard(e.detail.id));

  $('#btn-refresh').addEventListener('click', () => { closePanel(); loadAll(); });
  $('#btn-close').addEventListener('click', closePanel);
  $('#btn-save').addEventListener('click', save);
  $('#btn-render').addEventListener('click', rerender);
  $('#btn-delete').addEventListener('click', removeCard);
  $('#btn-art').addEventListener('click', uploadArtwork);

  watchResize();

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    // Escape closes the frontmost thing: a popover first, then the editor.
    // Closing both at once would make one keypress undo two decisions.
    const wasOpen = document.querySelector('.pop:not([hidden])');
    closeAllPopovers();
    if (!wasOpen) closePanel();
  });
}

/* The icon set and the schemas are awaited before the first paint: a form or a
 * filter panel built without them would silently show no icons and no controls.
 * The filter panel must exist before the first renderGrid(), because it owns
 * the predicate the grid filters through. */
async function boot() {
  wire();
  await Promise.all([loadIcons(), loadCodes()]);
  await initFilters($('#btn-filters'));
  await initNewCard($('#btn-new'), newCard);
  await loadAll();
}

boot().catch((err) => banner(String(err.message || err), 'error'));
