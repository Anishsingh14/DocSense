import { ApiError, getJob, listDocuments, queryDocuments, uploadDocument } from './api.js';
import { modeByKey, resolveStyle } from './modes.js';

/**
 * Chat page settings and the bridge to the DocSense backend (requests go through src/lib/api.js).
 *
 * For each question: make sure every uploaded file is stored on the server (a stored document with the
 * same file name is reused; otherwise the file is uploaded and the page waits for ingestion), then
 * POST /query and convert the response into the shape AnswerCard renders:
 * {
 *   "answer":   "text with **bold**, - bullets, 1. numbered items and [1] citations",
 *   "sources":  [{ "index": 1, "document": "file.pdf", "passage": "…", "page": 3 }],
 *   "provider": { "name": "Groq", "model": "model-name" },
 *   "style":    "summary" | "full"   (the answer style that was sent; see ANSWER_STYLES in modes.js)
 * }
 * Nothing here invents answers, sources or providers. Defining `window.DocSenseAPI.ask(ctx)` still
 * replaces the backend call entirely.
 */
export const CHAT_CONFIG = {
  api: {
    uploadTimeoutMs: 120000,    // sending one file
    ingestTimeoutMs: 1800000,   // waiting while the server reads, describes and stores it
    pollMs: 2000,               // how often to check an ingestion job
    queryTimeoutMs: 180000,     // one answer; the server may try several providers in turn
  },
  attachments: { enabled: false },   // the paperclip is shown but not wired to a backend
  providerLogos: {                   // matched against provider.name (lowercase, "contains")
    groq: '/assets/providers/groq.svg',
    nvidia: '/assets/providers/nvidia.svg',
    cohere: '/assets/providers/cohere.svg',
    openrouter: '/assets/providers/openrouter.svg',
    gemini: '/assets/providers/gemini.svg',
    google: '/assets/providers/gemini.svg',
  },
  providerNames: {                   // the backend reports the provider's env var name
    RAG_Groq: 'Groq',
    RAG_NVIDIA: 'NVIDIA',
    RAG_Cohere: 'Cohere',
    RAG_OpenRouter: 'OpenRouter',
    RAG_Gemini: 'Google Gemini',
    RAG_SiliconFlow: 'SiliconFlow',
    RAG_OpenCode_Console: 'OpenCode',
  },
  text: {
    notConnected: 'Could not reach the DocSense server. Make sure the backend is running, then try again.',
    failed: 'Something went wrong while getting the answer. Please try again.',
    busy: 'The AI services are busy right now. Please try again in about a minute.',
    timeout: 'The server took too long to respond. Please try again.',
    notFound: 'This document is no longer on the server. Ask again to upload it once more.',
    tooLarge: 'This file is larger than the server’s 25 MB limit.',
    unsupported: 'The server does not accept this file type.',
    unreadable: 'The document could not be read. It may be empty or damaged.',
    noText: 'No readable text was found in “{file}”.',
    ingestFailed: 'The server could not process “{file}”. Please try again.',
    preparing: 'Preparing “{file}”. Large files can take a few minutes; you can type your question now.',
    ready: '“{file}” is ready.',
    noteLabel: 'Note',
    styleGroup: 'Answer style',
    styleLocked: 'Legal Precision always quotes the exact clause text.',
    noSources: 'No sources available',
    noProvider: 'Provider information unavailable',
    noAttach: 'Attachments are not available yet.',
    noDocument: 'No document found. Upload a PDF first.',
  },
};

const MESSAGE_KEYS = {
  'not-connected': 'notConnected',
  busy: 'busy',
  timeout: 'timeout',
  'not-found': 'notFound',
  'too-large': 'tooLarge',
  unsupported: 'unsupported',
  unreadable: 'unreadable',
  'no-text': 'noText',
  'ingest-failed': 'ingestFailed',
  'no-document': 'noDocument',
};

/** The message to show for an error thrown by prepareDocuments() or askBackend(). */
export function describeError(err) {
  const key = MESSAGE_KEYS[err && err.code] || 'failed';
  return CHAT_CONFIG.text[key].replace('{file}', (err && err.file) || '');
}

/* ------------------------------------------------------------------ documents on the server */

// Failures that would repeat if the same file were sent again; they are remembered so a retry costs nothing.
const PERMANENT = new Set(['too-large', 'unsupported', 'unreadable', 'no-text']);
const prepared = new Map(); // file key -> Promise<doc_id>, kept for the life of the page
const fileKey = (f) => `${f.name}|${f.size}|${f.lastModified}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function failure(code, file) {
  const err = new ApiError(code);
  err.file = file;
  return err;
}

async function waitForJob(job, fileName) {
  const deadline = Date.now() + CHAT_CONFIG.api.ingestTimeoutMs;
  let current = job;
  let misses = 0;
  while (current.status === 'queued' || current.status === 'running') {
    if (Date.now() > deadline) throw failure('timeout', fileName);
    await sleep(CHAT_CONFIG.api.pollMs);
    try {
      current = await getJob(job.job_id);
      misses = 0;
    } catch (err) {
      // Ride out a short network blip; give up on anything else (a lost job is a 404).
      misses += 1;
      if ((err.code !== 'not-connected' && err.code !== 'timeout') || misses > 5) throw err;
    }
  }
  if (current.status === 'failed') {
    const unreadable = /^(DocumentParsingError|UnsupportedFileTypeError)\b/.test(current.error || '');
    throw failure(unreadable ? 'unreadable' : 'ingest-failed', fileName);
  }
  if (!current.chunks_stored) throw failure('no-text', fileName);
  return current.doc_id;
}

async function ingest(file, getStored, onStatus) {
  // The server names a document after its file, so a stored copy with this name is reused rather than
  // uploaded and processed again.
  const stored = await getStored();
  const existing = stored.find((d) => d.doc_name === file.name && d.chunk_count > 0);
  if (existing) return existing.doc_id;

  if (onStatus) onStatus({ state: 'preparing', file: file.name });
  const job = await uploadDocument(file, CHAT_CONFIG.api.uploadTimeoutMs);
  const docId = await waitForJob(job, file.name);
  if (onStatus) onStatus({ state: 'ready', file: file.name });
  return docId;
}

/**
 * Resolves to the server doc_id of every file, uploading only the files the server does not have.
 * Calls for the same file share one upload. onStatus({ state: 'preparing' | 'ready', file }) reports uploads.
 */
export function prepareDocuments(files, onStatus) {
  let listing = null;
  const getStored = () => {
    if (!listing) listing = listDocuments().then((r) => (r && Array.isArray(r.documents) ? r.documents : []));
    return listing;
  };
  return Promise.all(files.map((file) => {
    const key = fileKey(file);
    if (!prepared.has(key)) {
      const pending = ingest(file, getStored, onStatus);
      prepared.set(key, pending);
      pending.catch((err) => {
        if (!PERMANENT.has(err && err.code) && prepared.get(key) === pending) prepared.delete(key);
      });
    }
    return prepared.get(key);
  }));
}

/* ------------------------------------------------------------------ answers */

const CITE_GROUP = /\(\s*Source\s+\d+(?:\s*(?:,|;|&|and)\s*Source\s+\d+)*\s*\)/g;
const CITE_BOLD = /\*\*Source\s+(\d+)\*\*/g;
const CITE_TOKEN = /\bSource\s+(\d+)/g;

/**
 * Turns the backend's "(Source N)" markers into the clickable [N] markers RichText renders. Only numbers
 * of sources that were actually retrieved (1..count) are linked; any other text is left as written.
 */
export function linkCitations(text, count) {
  const ok = (n) => n >= 1 && n <= count;
  return String(text)
    .replace(CITE_GROUP, (group) => {
      const nums = [...group.matchAll(/Source\s+(\d+)/g)].map((m) => Number(m[1]));
      return nums.every(ok) ? nums.map((n) => `[${n}]`).join('') : group;
    })
    .replace(CITE_BOLD, (m, n) => (ok(Number(n)) ? `Source [${Number(n)}]` : m))
    .replace(CITE_TOKEN, (m, n) => (ok(Number(n)) ? `Source [${Number(n)}]` : m));
}

/** Converts a POST /query response (api/schemas.py QueryResponse) into AnswerCard's data. */
export function toAnswerData(res) {
  const evidence = res && res.evidence && Array.isArray(res.evidence.sources) ? res.evidence.sources : [];
  const citations = res && res.core && Array.isArray(res.core.citations) ? res.core.citations : [];
  const byNumber = new Map(evidence.map((s) => [s.source_number, s]));

  // The Sources panel lists the passages the answer cites, numbered as in the answer.
  const numbers = [...new Set(citations.map((c) => c.source_number))].sort((a, b) => a - b);
  const sources = numbers.map((n) => {
    const s = byNumber.get(n) || citations.find((c) => c.source_number === n) || {};
    return { index: n, document: s.doc_name || '', passage: s.text || '', page: s.page_num };
  });

  const meta = (res && res.meta) || {};
  let answer = linkCitations((res && res.core && res.core.answer) || '', evidence.length);
  const warning = meta.citation_check && meta.citation_check.warning;
  if (answer.trim() && warning) answer += `\n\n**${CHAT_CONFIG.text.noteLabel}:** ${warning}`;

  const id = meta.provider_used;
  const provider = id
    ? { name: CHAT_CONFIG.providerNames[id] || String(id).replace(/^RAG_/, '').replace(/_/g, ' '), model: meta.model_used || '' }
    : null;
  return { answer, sources, provider };
}

/** Sends one question to the backend and resolves to AnswerCard's data. Errors carry a `code` (see describeError). */
export async function askBackend({ question, mode, answerStyle, session, files, history }) {
  const style = resolveStyle(mode, answerStyle);
  const ctx = { question, mode, answerStyle: style, fileName: session.fileName || '', file: files[0] || null, files, history };
  if (window.DocSenseAPI && typeof window.DocSenseAPI.ask === 'function') return window.DocSenseAPI.ask(ctx);

  if (!files.length) throw new ApiError('no-document');
  const docIds = await prepareDocuments(files);
  const apiMode = (modeByKey(mode) || {}).api || 'single_doc';
  try {
    const res = await queryDocuments(
      { question, mode: apiMode, doc_ids: [...new Set(docIds)], answer_style: style },
      CHAT_CONFIG.api.queryTimeoutMs,
    );
    return { ...toAnswerData(res), style };
  } catch (err) {
    // The server no longer has a document (deleted, or its store was reset): forget it so the next question uploads it again.
    if (err && err.code === 'not-found') files.forEach((f) => prepared.delete(fileKey(f)));
    throw err;
  }
}
