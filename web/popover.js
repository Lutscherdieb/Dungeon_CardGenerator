/* A floating panel anchored to a button.
 *
 * Shared by the filter panel and the new-card dialog so the two behave the
 * same: open on click, close on Escape, close on a click outside, and keep the
 * button's aria-expanded honest.
 *
 * It floats over the grid rather than displacing it. That is the whole point:
 * the gallery must not reflow when a control opens -- reflowing is what made
 * the old edit drawer lose your place in 137 tiles.
 */

import { el } from './dom.js';

const open = new Set();

/** Build a popover anchored under `button`. Returns { root, body, show, hide, toggle }. */
export function popover(button, { title, width = 320, align = 'right' } = {}) {
  const body = el('div', { class: 'pop-body' });
  const root = el('div', {
    class: `pop pop-${align}`,
    role: 'dialog',
    'aria-label': title || 'panel',
    hidden: true,
    style: `width:${width}px`,
  },
    title ? el('header', { class: 'pop-head' }, el('strong', { text: title })) : null,
    body);

  document.body.append(root);

  const position = () => {
    const box = button.getBoundingClientRect();
    root.style.top = `${Math.round(box.bottom + 6)}px`;
    if (align === 'right') {
      root.style.right = `${Math.round(window.innerWidth - box.right)}px`;
      root.style.left = 'auto';
    } else {
      root.style.left = `${Math.round(box.left)}px`;
      root.style.right = 'auto';
    }
  };

  const api = {
    root,
    body,
    get isOpen() { return !root.hidden; },
    show() {
      position();
      root.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      open.add(api);
    },
    hide() {
      root.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      open.delete(api);
    },
    toggle() { root.hidden ? api.show() : api.hide(); },
  };

  button.addEventListener('click', (e) => { e.stopPropagation(); api.toggle(); });
  root.addEventListener('click', (e) => e.stopPropagation());
  window.addEventListener('resize', () => { if (!root.hidden) position(); });
  window.addEventListener('scroll', () => { if (!root.hidden) position(); }, true);

  return api;
}

/** Close every open popover. Wired once, in app.js. */
export function closeAllPopovers() {
  for (const p of [...open]) p.hide();
}

document.addEventListener('click', closeAllPopovers);
