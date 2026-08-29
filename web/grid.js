/* The card grid: tiles, the images they show, and which one is selected.
 *
 * This module knows nothing about the editor. Clicking a tile dispatches a
 * `card:select` event on the grid element and app.js decides what that means --
 * which is what keeps the module graph acyclic (the editor imports the grid,
 * never the other way round).
 */

import { $, el } from './dom.js';
import { state } from './state.js';

/** The predicate deciding which cards are shown. Replaced by setFilter(). */
let shows = () => true;

export function setFilter(predicate) {
  shows = predicate || (() => true);
}

/** The cards currently passing the filter, in grid order. */
export function shownCards() {
  return state.cards.filter(shows);
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

/** Grid uses the small thumbnail; the editor uses the full trim image. */
export function imageUrl(view, size = 'thumb') {
  if (view.render?.status === 'done' && view.render?.urls) {
    const url = view.render.urls[size] || view.render.urls.trim;
    return `${url}?v=${imageVersion(view)}`;
  }
  // Not rendered yet: show the artwork the card owns. There is no path to fall
  // back to any more -- the image lives in the store.
  return view.artwork?.url || null;
}

export function buildTile(view) {
  const url = imageUrl(view, 'thumb');
  const img = el('img', { alt: view.name, loading: 'lazy' });
  if (url) img.src = url; else img.style.background = '#000';
  img.addEventListener('error', () => {
    const fallback = view.artwork?.url;
    if (fallback && !img.src.includes('/artwork')) img.src = fallback;
  });

  const status = view.render?.queue || view.render?.status || 'pending';
  const selected = state.current?.id === view.id ? ' selected' : '';
  const select = () => $('#grid').dispatchEvent(
    new CustomEvent('card:select', { detail: { id: view.id } }));

  return el('article', {
    class: `card${selected}`, tabindex: '0', role: 'button', 'data-id': view.id,
    onclick: select,
    onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); } },
  },
    img,
    el('span', { class: `dot ${status}`, title: `render: ${status}` }),
    el('div', { class: 'meta' },
      el('strong', { text: view.name }),
      el('span', { text: view.subtype ? `${view.type} · ${view.subtype}` : view.type })),
  );
}

export function renderGrid() {
  const grid = $('#grid');
  grid.replaceChildren();
  const shown = shownCards();

  if (!shown.length) {
    grid.append(el('p', { class: 'hint', text: 'No cards. Use "New card", or run: python -m cardgen.cli import' }));
    return;
  }
  for (const view of shown) grid.append(buildTile(view));
}

/** Swap one tile in place. Selecting a card must never redraw the other 136 --
 *  that is what made the whole gallery flicker. */
export function replaceTile(view) {
  const tile = $(`#grid [data-id="${view.id}"]`);
  if (tile) tile.replaceWith(buildTile(view));
}

export function markSelected(id) {
  for (const tile of document.querySelectorAll('#grid .card.selected')) {
    tile.classList.remove('selected');
  }
  if (id !== null) $(`#grid [data-id="${id}"]`)?.classList.add('selected');
}
