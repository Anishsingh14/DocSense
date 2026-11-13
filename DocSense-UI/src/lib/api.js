/**
 * HTTP client for the DocSense FastAPI backend (api/main.py in the DocSense project).
 *
 * The browser calls `${API_BASE}/...` on this site's own origin. With `npm run dev` and `npm run preview`,
 * API_BASE is '/api' and vite.config.js forwards those requests to the backend (port 8000 by default),
 * so the backend needs no CORS change. To call a backend somewhere else, set VITE_API_BASE_URL
 * (for example in .env.local); that backend must then allow this site's origin in its CORS list.
 */
export const API_BASE = ((import.meta.env && import.meta.env.VITE_API_BASE_URL) || '/api').replace(/\/+$/, '');

/**
 * `code` is one of: not-connected, timeout, busy (503), not-found (404), too-large (413),
 * unsupported (415), rejected (422), server (other errors), plus the codes chatConfig.js adds.
 */
export class ApiError extends Error {
  constructor(code, { status = 0, detail = '' } = {}) {
    super(detail || code);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}

const CODES_BY_STATUS = { 404: 'not-found', 413: 'too-large', 415: 'unsupported', 422: 'rejected', 503: 'busy' };

async function request(path, { method = 'GET', json, form, timeoutMs = 30000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const init = { method, signal: ctrl.signal, headers: { Accept: 'application/json' } };
  if (json !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(json);
  } else if (form) {
    init.body = form; // the browser sets the multipart boundary
  }

  let res;
  let text = '';
  try {
    res = await fetch(`${API_BASE}${path}`, init);
    text = await res.text();
  } catch (err) {
    throw new ApiError(err && err.name === 'AbortError' ? 'timeout' : 'not-connected');
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }

  // Every backend endpoint answers with JSON. Anything else (an HTML page, or a 5xx with no JSON body
  // from the dev proxy) means the request never reached the backend.
  const isApiBody = data !== null && typeof data === 'object';
  if (res.ok) {
    if (!isApiBody) throw new ApiError('not-connected', { status: res.status });
    return data;
  }
  if (res.status >= 500 && !(isApiBody && 'detail' in data)) throw new ApiError('not-connected', { status: res.status });
  const detail = isApiBody && typeof data.detail === 'string' ? data.detail : '';
  throw new ApiError(CODES_BY_STATUS[res.status] || 'server', { status: res.status, detail });
}

/** GET /documents: every document stored on the server, as { documents: [{ doc_id, doc_name, doc_type, chunk_count, pages }] }. */
export const listDocuments = () => request('/documents');

/** POST /documents: queues ingestion and answers 202 with { job_id, doc_id, status }. */
export function uploadDocument(file, timeoutMs) {
  const form = new FormData();
  form.append('file', file, file.name);
  return request('/documents', { method: 'POST', form, timeoutMs });
}

/** GET /documents/jobs/{job_id}: { job_id, doc_id, status: queued|running|done|failed, chunks_stored, error }. */
export const getJob = (jobId) => request(`/documents/jobs/${encodeURIComponent(jobId)}`);

/** POST /query with { question, mode: single_doc|multi_doc|legal, doc_ids, answer_style }. */
export const queryDocuments = (body, timeoutMs) => request('/query', { method: 'POST', json: body, timeoutMs });
