/* The one way this frontend talks to the server.
 *
 * Every call goes through `api()`, so error shaping happens in exactly one
 * place: the server returns JSON errors (see web/app.py's _json_error), and a
 * non-JSON body is surfaced verbatim rather than swallowed -- an HTML error
 * page reaching a `.json()` call is how a broken endpoint turns into a silent
 * "undefined" in the UI.
 */

export async function api(path, options = {}) {
  const res = await fetch(path, options);
  const text = await res.text();
  let body = null;
  if (text) {
    try { body = JSON.parse(text); }
    catch { throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`); }
  }
  if (!res.ok) throw new Error(body?.error || `${res.status} ${res.statusText}`);
  return body;
}

export const getJSON = (p) => api(p);

export const sendJSON = (p, method, payload) => api(p, {
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});
