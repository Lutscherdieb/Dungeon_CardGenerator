/* Render state: what the card's PNG situation is, and polling while it changes.
 *
 * Polling starts only when a card actually has work in flight. It used to start
 * on every open, so 1.2s after selecting any card the first tick found it idle
 * and triggered a full gallery reload.
 */

import { getJSON } from './api.js';
import { $ } from './dom.js';
import { imageUrl } from './grid.js';

const POLL_MS = 1200;

let timer = null;

export function paintRenderState(view) {
  const status = view.render?.queue || view.render?.status || 'pending';
  const node = $('#render-state');
  if (!node) return;
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
  if (img && url) img.src = url;
}

export function isBusy(view) {
  const status = view.render?.queue || view.render?.status;
  return status === 'queued' || status === 'rendering';
}

/** Poll a card's render until it settles, then call `onSettled(id)`. */
export function startPolling(id, { isCurrent, onTick, onSettled }) {
  stopPolling();
  timer = setInterval(async () => {
    if (!isCurrent(id)) return stopPolling();
    const status = await getJSON(`/api/cards/${id}/render`).catch(() => null);
    if (!status) return;
    onTick?.(status);
    if (status.queue === 'queued' || status.queue === 'rendering') return;
    stopPolling();
    await onSettled?.(id);
  }, POLL_MS);
}

export function stopPolling() {
  if (timer) { clearInterval(timer); timer = null; }
}
