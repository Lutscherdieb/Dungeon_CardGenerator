/* Card-type metadata: the JSON Schemas the form is built from, and the print
 * profile the artwork advice is drawn from.
 *
 * Both are fetched once per type and cached -- they change only when the model
 * changes, which means a server restart.
 */

import { getJSON } from './api.js';

const schemas = {};   // type (lowercase) -> JSON Schema
const profiles = {};  // type (lowercase) -> print profile

export async function schemaFor(type) {
  const key = String(type || '').toLowerCase();
  if (!schemas[key]) schemas[key] = await getJSON(`/api/meta/schema?card_type=${key}`);
  return schemas[key];
}

export async function profileFor(type) {
  const key = String(type || '').toLowerCase();
  if (!profiles[key]) profiles[key] = await getJSON(`/api/meta/profile?card_type=${key}`);
  return profiles[key];
}

/** Every card type's schema, keyed by lowercase type name. */
export async function allSchemas() {
  const types = (await getJSON('/api/meta/types')).types;
  await Promise.all(types.map(schemaFor));
  return Object.fromEntries(types.map((t) => [t, schemas[t]]));
}

/** Resolve a local $ref against the schema's own $defs. */
export function deref(schema, node) {
  if (!node || !node.$ref) return node;
  const name = node.$ref.replace('#/$defs/', '');
  return schema.$defs?.[name] || node;
}

/** A blank card of this type: every property at its declared default.
 *
 * Derived from the schema so a new field on the model gets a sane starting
 * value with no edit here.
 */
export function blankCard(schema) {
  const card = {};
  for (const [key, spec] of Object.entries(schema.properties || {})) {
    if (spec.const !== undefined) card[key] = spec.const;
    else if (spec.default !== undefined) card[key] = spec.default;
    else {
      const resolved = deref(schema, spec);
      if (resolved.enum) card[key] = resolved.enum[0];
      else if (resolved.type === 'integer') card[key] = resolved.minimum ?? 0;
      else if (resolved.type === 'array') card[key] = [];
      else if (resolved.type === 'boolean') card[key] = false;
      else card[key] = '';
    }
  }
  return card;
}
