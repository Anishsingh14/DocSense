/**
 * Hand-off between the Get Started page and the Chat page.
 * Small details go to sessionStorage; the PDF files themselves go to IndexedDB so they survive a refresh.
 */
export const SESSION_KEY = 'docsense.session';
const DB_NAME = 'docsense';
const STORE = 'files';

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveSession({ mode, modeLabel, files }) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      mode,
      modeLabel,
      fileName: files[0].name,
      fileSize: files[0].size,
      fileNames: files.map((f) => f.name),
    }));
  } catch (e) { /* storage unavailable: ignore */ }

  try {
    const db = await openDb();
    await new Promise((resolve) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(files[0], 'current');
      tx.objectStore(STORE).put(files, 'all');
      tx.oncomplete = resolve;
      tx.onerror = resolve;
      tx.onabort = resolve;
    });
  } catch (e) { /* IndexedDB unavailable: the chat page just won't have the files */ }
}

/* The Chat page's answer style choice (Summary / Exact quotes), kept for the rest of the browser session. */
const STYLE_KEY = 'docsense.answerStyle';

export function loadAnswerStyle() {
  try {
    return sessionStorage.getItem(STYLE_KEY) || '';
  } catch (e) {
    return '';
  }
}

export function saveAnswerStyle(style) {
  try { sessionStorage.setItem(STYLE_KEY, style); } catch (e) { /* storage unavailable: ignore */ }
}

export function loadSessionMeta() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || '{}');
  } catch (e) {
    return {};
  }
}

/** Resolves to an array of the uploaded File objects (empty if none were stored). */
export async function loadFiles() {
  try {
    const db = await openDb();
    return await new Promise((resolve) => {
      const store = db.transaction(STORE).objectStore(STORE);
      const all = store.get('all');
      all.onsuccess = () => {
        if (Array.isArray(all.result) && all.result.length) { resolve(all.result); return; }
        const cur = store.get('current');
        cur.onsuccess = () => resolve(cur.result ? [cur.result] : []);
        cur.onerror = () => resolve([]);
      };
      all.onerror = () => resolve([]);
    });
  } catch (e) {
    return [];
  }
}
