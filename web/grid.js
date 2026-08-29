/* The card grid: tiles, the images they show, which one is selected, and where
 * the inline editor sits.
 *
 * This module knows nothing about what the editor contains. Clicking a tile
 * dispatches a `card:select` event on the grid element and app.js decides what
 * that means -- which is what keeps the module graph acyclic (the editor
 * imports the grid, never the other way round).
 */

import { $, el } from './dom.js';
import { state } from './state.js';

/** The predicate deciding which cards are shown. Replaced by setFilter(). */
let shows = () => true;

/** The card the editor is open on, or null. Placement state, not app state. */
let editorFor = null;

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
  const editor = $('#editor');
  const shown = shownCards();

  // Detach the editor first: it is a permanent child of the grid, and
  // replaceChildren() would otherwise destroy the open form.
  editor.remove();
  grid.replaceChildren();

  if (!shown.length) {
    grid.append(el('p', { class: 'hint', text: 'No cards match. Clear the filters, use "New card", or run: python -m cardgen.cli import' }));
  }
  for (const view of shown) grid.append(buildTile(view));

  grid.append(editor);          // parked at the end; placeEditor moves it
  placeEditor(editorFor);
  $('#shown-count').textContent =
    shown.length === state.cards.length ? '' : `${shown.length} of ${state.cards.length}`;
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

/* ---------- inline editor placement ---------- */

/** How many columns the grid is currently laid out in.
 *
 * Measured, never predicted. The grid is `repeat(auto-fill, minmax(190px, 1fr))`,
 * so the count follows the container width and the viewport in a way no
 * arithmetic here could track; reading the resolved track list is the only
 * honest answer. (tests/check_gallery.py samples the same property.)
 */
function columnCount(grid) {
  const tracks = getComputedStyle(grid).gridTemplateColumns;
  return tracks && tracks !== 'none' ? tracks.split(' ').length : 1;
}

/** Put the editor on the row directly below the card it belongs to.
 *
 * Called with a card id to show it there, or null to hide it. Hidden, the
 * section is `display: none` and occupies no grid track at all.
 *
 * The grid's WIDTH never changes when the editor opens -- it is a grid item,
 * not an overlay and not a drawer that steals horizontal space -- so the column
 * count is untouched and no tile moves sideways. Tiles below simply shift down,
 * and the scroll position is anchored on the selected tile so the card you
 * clicked stays exactly where it was under the cursor.
 */
export function placeEditor(cardId) {
  editorFor = cardId;
  const grid = $('#grid');
  const editor = $('#editor');

  if (cardId === null || cardId === undefined) {
    editor.hidden = true;
    grid.append(editor);
    return;
  }

  const tiles = [...grid.querySelectorAll('.card')];
  const index = tiles.findIndex((t) => Number(t.dataset.id) === cardId);
  if (index < 0) {                 // filtered out of view
    editor.hidden = true;
    grid.append(editor);
    return;
  }

  const anchor = tiles[index].getBoundingClientRect().top;

  const cols = columnCount(grid);
  const nextRowStart = (Math.floor(index / cols) + 1) * cols;
  editor.hidden = false;
  if (nextRowStart < tiles.length) grid.insertBefore(editor, tiles[nextRowStart]);
  else grid.append(editor);

  // Keep the clicked tile under the cursor. Opening the editor above it would
  // otherwise push it down by the editor's full height.
  const moved = tiles[index].getBoundingClientRect().top - anchor;
  if (moved) window.scrollBy(0, moved);
}

/** Re-place the editor when the column count changes under it.
 *
 * A resize can move the selected tile to a different row, which would leave
 * the editor stranded mid-grid. Throttled to one animation frame so a drag-
 * resize does not run the row maths per pixel.
 */
export function watchResize() {
  let queued = false;
  window.addEventListener('resize', () => {
    if (queued || editorFor === null) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; placeEditor(editorFor); });
  });
}
