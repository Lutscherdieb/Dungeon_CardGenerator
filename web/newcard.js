/* The "New card" dialog: pick a type, name it, create it.
 *
 * Replaces a window.prompt() that asked for the type as free text and matched
 * it case-insensitively against the type list -- a typo produced an error
 * banner, and the list of valid answers was only visible inside the prompt.
 * The type comes from /api/meta/types, so a ninth card type appears here with
 * no edit to this file.
 */

import { getJSON } from './api.js';
import { el } from './dom.js';
import { popover } from './popover.js';

/** Wire the dialog to its button. `onCreate({type, name})` does the work. */
export async function initNewCard(button, onCreate) {
  const { types } = await getJSON('/api/meta/types');
  const pop = popover(button, { title: 'New card', width: 260 });

  const typeSelect = el('select', {},
    ...types.map((t) => el('option', { value: t, text: t[0].toUpperCase() + t.slice(1) })));
  const nameInput = el('input', { type: 'text', placeholder: 'Card name' });

  const submit = async () => {
    const name = nameInput.value.trim();
    if (!name) { nameInput.focus(); return; }
    pop.hide();
    nameInput.value = '';
    await onCreate({ type: typeSelect.value, name });
  };

  nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });

  pop.body.append(
    el('label', { class: 'field' }, el('span', { class: 'field-label', text: 'Type' }), typeSelect),
    el('label', { class: 'field' }, el('span', { class: 'field-label', text: 'Name' }), nameInput),
    el('div', { class: 'filter-foot' },
      el('button', { type: 'button', class: 'btn small primary', text: 'Create', onclick: submit })),
  );

  // The name is what you type first, every time.
  button.addEventListener('click', () => { if (pop.isOpen) setTimeout(() => nameInput.focus(), 0); });
  return pop;
}
