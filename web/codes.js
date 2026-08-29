/* The [] icon codes a Description may use.
 *
 * Fetched from /api/meta/tokens, which serves the very table
 * cardgen.render.symbols substitutes with -- so this legend cannot offer a code
 * that would print as literal text on the card, and a token added to that table
 * appears here with no edit to this file.
 *
 * Two ways to reach it, because they answer different questions:
 *   - the Description row's tooltip lists every code as text ("what exists?"),
 *     matching the tooltip convention every other field already uses;
 *   - the "codes" toggle opens an icon legend and clicking one inserts it at
 *     the cursor ("put it in for me, spelled right").
 */

import { getJSON } from './api.js';
import { el } from './dom.js';

let tokens = [];

export async function loadCodes() {
  const res = await getJSON('/api/meta/tokens').catch(() => ({ tokens: [] }));
  tokens = res.tokens || [];
}

/** Every code as one tooltip string. */
export function codesTooltip() {
  if (!tokens.length) return 'Inline icons: type a code in square brackets.';
  return 'Inline icons — type the code in square brackets:\n'
    + tokens.map((t) => t.code).join('  ');
}

/** Insert `text` at the cursor in `field`, keeping focus and undo behaviour. */
function insertAtCursor(field, text) {
  const start = field.selectionStart ?? field.value.length;
  const end = field.selectionEnd ?? field.value.length;
  field.focus();
  // setRangeText keeps the browser's own undo stack intact; rebuilding
  // field.value by hand does not.
  field.setRangeText(text, start, end, 'end');
  field.dispatchEvent(new Event('input', { bubbles: true }));
}

/** The legend: a toggle plus the icon list it reveals, bound to one textarea. */
export function codesLegend(textarea) {
  const list = el('div', { class: 'codes', hidden: true },
    ...tokens.map((t) => el('button', {
      type: 'button',
      class: 'code',
      title: `insert ${t.code}`,
      onclick: (e) => { e.preventDefault(); insertAtCursor(textarea, t.code); },
    },
      el('img', { class: 'icon', src: `/assets/${t.icon}`, alt: '', 'aria-hidden': 'true' }),
      el('span', { text: t.code }))));

  const toggle = el('button', {
    type: 'button',
    class: 'btn small codes-toggle',
    text: 'codes',
    'aria-expanded': 'false',
    onclick: (e) => {
      e.preventDefault();
      list.hidden = !list.hidden;
      toggle.setAttribute('aria-expanded', String(!list.hidden));
    },
  });

  return { toggle, list };
}
