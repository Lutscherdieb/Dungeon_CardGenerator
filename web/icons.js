/* The icon a name prints on the card.
 *
 * Derived, not listed: the templates resolve every icon as
 * `assets/<name lowercased>.png` (`assets/defence.png`, `assets/{{ Faction|lower }}.png`),
 * and /api/meta/icons says which of those files exist. So a field, an enum
 * value or a creature type shows its real printed icon, and a PNG dropped into
 * assets/ starts appearing here with no edit to this file.
 */

import { getJSON } from './api.js';
import { el } from './dom.js';

/** The asset stems that exist, filled once by loadIcons(). */
const stems = new Set();

/** Fetched once at boot. A form built before this lands would simply show no
 *  icons, so it is awaited ahead of the first paint rather than guarded for at
 *  every call site. */
export async function loadIcons() {
  const { icons } = await getJSON('/api/meta/icons').catch(() => ({ icons: [] }));
  stems.clear();
  for (const stem of icons) stems.add(stem);
}

export function hasIcon(name) {
  return stems.has(String(name ?? '').toLowerCase());
}

export function iconFor(name) {
  const stem = String(name ?? '').toLowerCase();
  if (!stems.has(stem)) return null;
  return el('img', { class: 'icon', src: `/assets/${stem}.png`, alt: '', 'aria-hidden': 'true' });
}

/** Fill an icon slot with the first of `names` that has one. A field is tried
 *  by its key first (Mana -> mana.png), then by its value, which is what gives
 *  Faction=Demon the demon icon and Type=Spell the spell icon. */
export function paintIcon(slot, ...names) {
  for (const name of names) {
    const img = iconFor(name);
    if (img) { slot.replaceChildren(img); return; }
  }
  slot.replaceChildren();
}
