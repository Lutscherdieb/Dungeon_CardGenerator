const API = location.origin + '/api';

const feed        = document.getElementById('feed');
const modal       = document.getElementById('modal');
const editor      = document.getElementById('jsonEditor');
const modalTitle  = document.getElementById('modal-title');
const saveBtn     = document.getElementById('saveBtn');
const cancelBtn   = document.getElementById('cancelBtn');
const refreshBtn  = document.getElementById('refresh');

const newBtn      = document.getElementById('newCardBtn');
const newModal    = document.getElementById('newModal');
const newEditor   = document.getElementById('newJson');
const newCreate   = document.getElementById('newCreate');
const newCancel   = document.getElementById('newCancel');

const uploadFilesBtn  = document.getElementById('uploadFilesBtn');
const uploadFolderBtn = document.getElementById('uploadFolderBtn');
const filePicker      = document.getElementById('filePicker');
const folderPicker    = document.getElementById('folderPicker');
const bgFile          = document.getElementById('bgFile');

let currentCard = null;

/* ---------- utils ---------- */
function escapeHtml(s){ return String(s ?? '').replace(/[&<>"']/g, m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m])); }
function open(el){ el.style.display = 'flex'; }
function close(el){ el.style.display = 'none'; }

async function safeJson(res) {
  const text = await res.text();
  try { return JSON.parse(text); }
  catch {
    throw new Error(`Expected JSON, got:\n${text.slice(0, 400)}`);
  }
}

/* ---------- API ---------- */
async function fetchCards() {
  const res = await fetch(`${API}/cards`, { headers: { 'Accept': 'application/json' } });
  if (!res.ok) {
    const msg = await res.text().catch(()=> `${res.status} ${res.statusText}`);
    throw new Error(`GET /cards failed: ${res.status} ${res.statusText}\n${msg}`);
  }
  return await safeJson(res);
}

/* ---------- image preference + fallback ---------- */
/** Returns array of candidate URLs in priority: trim > full > safe > background */
function imageCandidates(c) {
  const candidates = [];
  const bg = c.background ? c.background.replace('./','/').replace(/\\/g,'/') : null;

  if (c.last_png_path) {
    const p = c.last_png_path.replace('./','/').replace(/\\/g,'/');
    // derive siblings from the known naming convention
    const stem = p.replace(/(_safe|_trim)?\.png$/i, '');
    candidates.push(`${stem}_trim.png`);
    candidates.push(`${stem}.png`);
    candidates.push(`${stem}_safe.png`);
  }
  if (bg) candidates.push(bg);
  // final fallback
  candidates.push('/assets/placeholder.png');
  return candidates;
}

function setBestImage(img, c) {
  const list = imageCandidates(c);
  let i = 0;
  function tryNext() {
    if (i >= list.length) return;
    const url = list[i++];
    // add cache-buster for rendered images (everything except background/placeholder)
    const bust = (/_safe\.png$|_trim\.png$|\.png$/i.test(url) && !/placeholder\.png$/.test(url)) ? (`?t=${Date.now()}`) : '';
    img.src = url + bust;
  }
  img.onerror = tryNext;
  tryNext();
}

/* ---------- DOM ---------- */
function openEditModal(card, data) {
  currentCard = card;
  modalTitle.textContent = `Edit: #${card.id} — ${card.name || '(untitled)'}`;
  editor.value = JSON.stringify(data, null, 2);
  open(modal);
}
cancelBtn.onclick = () => close(modal);

function domItem(c) {
  const el = document.createElement('article');
  el.className = 'item';
  el.dataset.id = c.id;

  const img = document.createElement('img');
  img.className = 'thumb';
  img.alt = c.name || '';

  // preferred image with fallbacks
  setBestImage(img, c);

  const overlay = document.createElement('div');
  overlay.className = 'overlay';
  overlay.innerHTML = `
    <div class="o-name">${escapeHtml(c.name || '(untitled)')}</div>
    <div class="o-actions">
      <button class="chip" data-action="edit">Edit JSON / Upload</button>
    </div>
  `;

  el.appendChild(img);
  el.appendChild(overlay);

  overlay.querySelector('[data-action="edit"]').onclick = async () => {
    const res = await fetch(`${API}/cards/${c.id}`, { headers:{'Accept':'application/json'} });
    const data = await res.json();
    openEditModal(c, data);
  };

  // store reference to thumbnail for later updates
  el._thumb = img;
  return el;
}

function renderFeed(cards) {
  // newest first
  cards.sort((a,b) => (b.id||0) - (a.id||0));
  feed.innerHTML = '';
  for (const c of cards) feed.appendChild(domItem(c));
}

async function load() {
  try {
    const cards = await fetchCards();
    renderFeed(cards);
  } catch (e) {
    console.error(e);
    feed.innerHTML = `<div style="padding:16px;color:#ffb4b4;">${String(e).replace(/</g,'&lt;')}</div>`;
  }
}
function imageCandidates(c) {
  const candidates = [];
  const bg = c.background ? c.background.replace('./','/').replace(/\\/g,'/') : null;

  if (c.last_png_path) {
    const p = c.last_png_path.replace('./','/').replace(/\\/g,'/');
    const stem = p.replace(/(_safe|_trim)?\.png$/i, '');
    candidates.push(`${stem}_trim.png`);
    candidates.push(`${stem}.png`);
    candidates.push(`${stem}_safe.png`);
  }
  if (bg) candidates.push(bg);
  candidates.push('/assets/placeholder.png');
  return candidates;
}

/* ---------- Import (files/folder) ---------- */
async function uploadParts(fileList) {
  if (!fileList || !fileList.length) return;
  const fd = new FormData();
  for (const f of fileList) fd.append('files', f, f.name);
  const res = await fetch(`${API}/cards/importjson`, { method:'POST', body: fd });
  if (!res.ok) {
    const msg = await res.text().catch(()=> `${res.status} ${res.statusText}`);
    alert(`Import failed: ${msg}`);
    return;
  }
  await safeJson(res); // contains imported IDs; we simply reload
  await load();
}

/* ---------- Create new (manual JSON) ---------- */
function openNewModal(){ open(newModal); }
newCancel.onclick = () => close(newModal);

newCreate.onclick = async () => {
  let payload;
  try { payload = JSON.parse(newEditor.value); }
  catch (e) { alert('Invalid JSON: ' + e.message); return; }

  newCreate.disabled = true;
  try {
    const res = await fetch(`${API}/cards`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const msg = await res.text();
      alert(`Create failed:\n${msg}`);
      return;
    }
    await res.json();
    await load();
    close(newModal);
  } finally { newCreate.disabled = false; }
};

/* ---------- Save edits (auto-render via server queue) ---------- */
saveBtn.onclick = async () => {
  if (!currentCard) return;
  let payload;
  try { payload = JSON.parse(editor.value); }
  catch (e) { alert('Invalid JSON: ' + e.message); return; }

  saveBtn.disabled = true;
  try {
    const res = await fetch(`${API}/cards/${currentCard.id}`, {
      method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const t = await res.text();
      alert('Save failed:\n' + t);
      return;
    }
    // just reload; thumbnails choose best rendered image automatically
    await load();
    close(modal);
  } finally { saveBtn.disabled = false; }
};

/* ---------- Upload background (from edit modal) ---------- */
bgFile?.addEventListener('change', async (e) => {
  if (!currentCard) return;
  const file = e.target.files?.[0];
  if (!file) return;

  const fd = new FormData();
  fd.append('file', file, file.name);

  try {
    const res = await fetch(`${API}/cards/${currentCard.id}/upload_bg`, { method:'POST', body: fd });
    if (!res.ok) { alert('Upload failed:\n' + await res.text()); return; }
    await res.json();
    await load();
  } finally {
    e.target.value = '';
  }
});

/* ---------- Wire up top bar + loaders ---------- */
refreshBtn.onclick = load;
newBtn.onclick = openNewModal;
uploadFilesBtn.onclick  = () => filePicker.click();
uploadFolderBtn.onclick = () => folderPicker.click();

filePicker.addEventListener('change', async (e) => { await uploadParts(e.target.files); e.target.value=''; });
folderPicker.addEventListener('change', async (e) => { await uploadParts(e.target.files); e.target.value=''; });

window.addEventListener('keydown', (e) => { if (e.key === 'Escape') { close(modal); close(newModal);} });

/* Kick off */
load();
