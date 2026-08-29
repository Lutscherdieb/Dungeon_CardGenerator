/* Loading cards into the state cache and keeping the grid in step with it.
 *
 * Separate from grid.js because these two functions do I/O; grid.js is a pure
 * view over whatever the cache holds.
 */

import { getJSON } from './api.js';
import { renderGrid, replaceTile } from './grid.js';
import { cacheCard, state } from './state.js';

/** Fetch the whole deck and repaint the grid.
 *
 * Fires `cards:loaded` on `document` between filling the cache and painting,
 * so chrome that offers choices derived from the deck (the type filter) can
 * rebuild itself before the grid is drawn through it. An event rather than a
 * direct call: this module must not import the chrome that listens.
 */
export async function loadAll() {
  const { cards } = await getJSON('/api/cards');
  state.cards = cards;
  document.dispatchEvent(new CustomEvent('cards:loaded', { detail: { cards } }));
  renderGrid();
  return cards;
}

/** Refetch ONE card, update the cache and swap just its tile.
 *
 *  Returns the fresh view, or null if it could not be fetched -- callers that
 *  also show the card (the editor) repaint themselves from the return value,
 *  so this function does not need to know they exist.
 */
export async function refreshCard(id) {
  const view = await getJSON(`/api/cards/${id}`).catch(() => null);
  if (!view) return null;
  cacheCard(view);
  replaceTile(view);
  return view;
}
