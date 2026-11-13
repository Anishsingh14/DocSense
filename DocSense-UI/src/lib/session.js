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

/*
 * The Chat page's conversation, kept across visits under docsense_chat_v1: the mode, the document IDs and the
 * last MAX_SAVED_MESSAGES questions and answers (with citations, sources, provider and warning). Only those
 * listed fields are written, so no access code or key can end up in storage.
 */
const CHAT_KEY = 'docsense_chat_v1';
export const MAX_SAVED_MESSAGES = 50;
const EMPTY_CHAT = { mode: '', docIds: [], messages: [] };
const str = (v) => (typeof v === 'string' ? v : '');

function cleanAnswer(d) {
  return {
    answer: str(d.answer),
    citations: (Array.isArray(d.citations) ? d.citations : []).map((c) => ({
      source_number: c && c.source_number, doc_name: str(c && c.doc_name), page_num: c && c.page_num,
    })),
    sources: (Array.isArray(d.sources) ? d.sources : []).map((s) => ({
      index: s && s.index, document: str(s && s.document), passage: str(s && s.passage), page: s && s.page,
    })),
    provider: d.provider && typeof d.provider === 'object' ? { name: str(d.provider.name), model: str(d.provider.model) } : null,
    warning: str(d.warning) || null,
    style: str(d.style) || undefined,
  };
}

/** Questions, answers and errors only (never the loading placeholder), trimmed to the last MAX_SAVED_MESSAGES. */
function cleanMessages(list) {
  const out = [];
  (Array.isArray(list) ? list : []).forEach((m) => {
    if (!m || typeof m !== 'object') return;
    if ((m.type === 'user' || m.type === 'error') && typeof m.text === 'string') out.push({ type: m.type, text: m.text });
    else if (m.type === 'answer' && m.data && typeof m.data.answer === 'string') out.push({ type: 'answer', data: cleanAnswer(m.data) });
  });
  const kept = out.slice(-MAX_SAVED_MESSAGES);
  while (kept.length && kept[0].type !== 'user') kept.shift(); // don't start with a reply whose question was cut off
  return kept;
}

/** The saved chat as { mode, docIds, messages }; empty values if nothing valid is stored. */
export function loadChat() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHAT_KEY) || 'null');
    if (!raw || typeof raw !== 'object') return EMPTY_CHAT;
    return {
      mode: str(raw.mode),
      docIds: Array.isArray(raw.docIds) ? raw.docIds.filter((id) => typeof id === 'string') : [],
      messages: cleanMessages(raw.messages),
    };
  } catch (e) {
    return EMPTY_CHAT;
  }
}

export function saveChat({ mode, docIds, messages }) {
  try {
    localStorage.setItem(CHAT_KEY, JSON.stringify({ v: 1, mode, docIds, messages: cleanMessages(messages) }));
  } catch (e) { /* storage full or unavailable: the chat just isn't saved */ }
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
