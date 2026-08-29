/* The gallery's shared state.
 *
 * One mutable object rather than a store with actions: this is a single-user
 * local tool with one open card at a time, and the modules that write to it are
 * few and named below. Anything more would be ceremony.
 *
 *   cards    every card view from GET /api/cards, in server order
 *   current  the card the editor is open on, or null
 *   draft    an edited copy of current.card -- what Save sends
 */

export const state = {
  cards: [],
  current: null,
  draft: null,
};

/** Replace one card in the cache, appending if it is new. Returns its index. */
export function cacheCard(view) {
  const i = state.cards.findIndex((c) => c.id === view.id);
  if (i >= 0) state.cards[i] = view; else state.cards.push(view);
  return i >= 0 ? i : state.cards.length - 1;
}
