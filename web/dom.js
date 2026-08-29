/* DOM primitives shared by every view module.
 *
 * `banner()` lives here rather than in app.js on purpose: several modules need
 * to raise a message, and importing them from app.js would make the module
 * graph cyclic (app.js imports all of them). It is the one piece of page chrome
 * this file knows about, and it is documented as such.
 */

export const $ = (sel) => document.querySelector(sel);

export function el(tag, props = {}, ...children) {
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

export function banner(message, tone = 'warn') {
  const node = $('#banner');
  if (!message) { node.hidden = true; return; }
  node.hidden = false;
  node.textContent = message;
  node.style.color = tone === 'error' ? 'var(--danger)' : 'var(--warn)';
}

/** Human file size. A 23KB upload reading "0.0 MB" is not a size. */
export function fileSize(bytes) {
  if (!bytes && bytes !== 0) return '?';
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}
