import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePage } from '../hooks/usePage';
import { useToast } from '../hooks/useToast';
import Waves from '../components/common/Waves';
import AnswerCard from '../components/chat/AnswerCard';
import { CHAT_CONFIG, askBackend, describeError, keepStoredDocIds, prepareDocuments } from '../lib/chatConfig';
import { ANSWER_STYLES, DEFAULT_MODE, isMultiFile, modeByKey, resolveStyle } from '../lib/modes';
import { loadAnswerStyle, loadChat, loadFiles, loadSessionMeta, saveAnswerStyle, saveChat } from '../lib/session';
import '../styles/chat.css';

const AiAvatar = ({ loading }) => (
  <span className={`ch-avatar-ai${loading ? ' is-loading' : ''}`}>
    <img alt="DocSense" src="/assets/docsense-logo.png" />
  </span>
);

const UserAvatar = () => (
  <span className="ch-avatar-user">
    <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0z" /></svg>
  </span>
);

const DocIcon = ({ className }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </svg>
);

/* Mode icons for the header pill: the same drawings as the Get Started page's mode bar. */
const MODE_ICONS = {
  general: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 3C6.9 3 3 6.6 3 11c0 2.3 1 4.3 2.7 5.8L5 21l4.2-2c.9.3 1.8.4 2.8.4 5.1 0 9-3.6 9-8s-3.9-8.4-9-8.4Zm-4 6.2h8v1.6H8V9.2Zm0 3.2h5.5V14H8v-1.6Z" />
    </svg>
  ),
  multi: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </svg>
  ),
  legal: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M7 21h10M5 7h14" />
      <path d="M5 7 2.5 14a3 3 0 0 0 5 0Z M19 7l-2.5 7a3 3 0 0 0 5 0Z" />
    </svg>
  ),
};

/* Icons for the answer style toggle: short lines for Summary, quotation marks for Exact quotes. */
const STYLE_ICONS = {
  summary: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
      <path d="M4 7h16M4 12h11M4 17h7" />
    </svg>
  ),
  full: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5.5 7H10v6H5.5A1.5 1.5 0 0 1 4 11.5v-3A1.5 1.5 0 0 1 5.5 7ZM15.5 7H20v6h-4.5a1.5 1.5 0 0 1-1.5-1.5v-3A1.5 1.5 0 0 1 15.5 7Z" fill="currentColor" />
      <path d="M10 13c0 2.6-1.6 4.2-4.2 4.7M20 13c0 2.6-1.6 4.2-4.2 4.7" />
    </svg>
  ),
};

let nextId = 1;

export default function Chat() {
  usePage({ page: 'chat', title: 'Ask your document | DocSense', themeColor: '#D3D4C0' });

  const session = useMemo(() => loadSessionMeta(), []);
  const saved = useMemo(() => loadChat(), []);
  // The mode chosen on Get Started in this tab wins; otherwise the saved chat's mode; otherwise the default.
  const mode = modeByKey(session.mode) ? session.mode : (modeByKey(saved.mode) ? saved.mode : DEFAULT_MODE);
  const modeLabel = (mode === session.mode && session.modeLabel) || modeByKey(mode).label;
  const pickDocument = isMultiFile(mode);
  const styleLocked = !!modeByKey(mode).styleLocked;
  const [answerStyle, setAnswerStyle] = useState(() => resolveStyle(mode, loadAnswerStyle()));

  const [files, setFiles] = useState([]);
  const [urls, setUrls] = useState({});
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [messages, setMessages] = useState(() => saved.messages.map((m) => ({ ...m, id: nextId++ })));
  const [docIds, setDocIds] = useState(saved.docIds);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [toast, showToast] = useToast(2800);
  const history = useRef(null);
  if (history.current === null) {
    history.current = saved.messages
      .filter((m) => m.type !== 'error')
      .map((m) => (m.type === 'user' ? { role: 'user', content: m.text } : { role: 'assistant', content: m.data.answer }));
  }
  const textareaRef = useRef(null);

  const started = messages.length > 0;

  /* The uploaded files (kept in IndexedDB by the Get Started page) */
  useEffect(() => {
    let cancelled = false;
    const created = [];
    loadFiles().then((list) => {
      if (cancelled) return;
      const map = {};
      list.forEach((f) => {
        const url = URL.createObjectURL(f);
        created.push(url);
        map[f.name] = url;
      });
      setFiles(list);
      setUrls(map);
      // Start sending the files to the server now, so they are usually ready by the first question.
      if (list.length) {
        prepareDocuments(list, ({ state, file }) => {
          if (!cancelled) showToast(CHAT_CONFIG.text[state].replace('{file}', file));
        })
          .then((ids) => { if (!cancelled) setDocIds([...new Set(ids)]); })
          .catch((err) => { if (!cancelled) showToast(describeError(err)); });
      }
    });
    return () => {
      cancelled = true;
      created.forEach((u) => URL.revokeObjectURL(u));
    };
  }, []);

  useEffect(() => {
    if (!session.fileName && !saved.docIds.length) showToast(CHAT_CONFIG.text.noDocument);
    textareaRef.current?.focus({ preventScroll: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Saved chat: forget saved document IDs the server no longer returns */
  useEffect(() => {
    let cancelled = false;
    if (saved.docIds.length) {
      keepStoredDocIds(saved.docIds).then((kept) => {
        const gone = saved.docIds.filter((id) => !kept.includes(id));
        if (!cancelled && gone.length) setDocIds((cur) => cur.filter((id) => !gone.includes(id)));
      });
    }
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Saved chat: write the mode, document IDs and messages after every change */
  useEffect(() => {
    saveChat({ mode, docIds, messages });
  }, [mode, docIds, messages]);

  /* Page-level state classes used by the stylesheet (centred prompt, preview open) */
  useEffect(() => {
    document.body.classList.toggle('is-initial', !started);
    return () => document.body.classList.remove('is-initial');
  }, [started]);
  useEffect(() => {
    document.body.classList.toggle('preview-open', previewOpen);
    return () => document.body.classList.remove('preview-open');
  }, [previewOpen]);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setPreviewOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  /* Grow the textarea with its content */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  /* Keep the newest message in view */
  useEffect(() => {
    if (messages.length) window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const urlFor = useCallback((docName) => {
    if (docName && urls[docName]) return urls[docName];
    return !docName && files.length ? urls[files[0].name] || '' : '';
  }, [urls, files]);

  const submit = async (e) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setBusy(true);
    setInput('');
    const loadingId = nextId++;
    setMessages((m) => [...m, { id: nextId++, type: 'user', text: q }, { id: loadingId, type: 'loading' }]);
    history.current.push({ role: 'user', content: q });

    let reply;
    try {
      const { docIds: usedIds, ...data } = (await askBackend({
        question: q, mode, answerStyle, session, files, docIds, history: history.current.slice(0, -1),
      })) || {};
      if (typeof data.answer !== 'string' || !data.answer.trim()) throw new Error('empty');
      if (Array.isArray(usedIds) && usedIds.length) setDocIds(usedIds);
      history.current.push({ role: 'assistant', content: data.answer });
      reply = { id: loadingId, type: 'answer', data };
    } catch (err) {
      reply = {
        id: loadingId,
        type: 'error',
        text: describeError(err),
      };
    }
    setMessages((m) => m.map((x) => (x.id === loadingId ? reply : x)));
    setBusy(false);
    textareaRef.current?.focus();
  };

  /* Clear chat: empties the conversation on screen and in the saved chat (the mode and documents stay). */
  const clearChat = () => {
    if (busy) return;
    setMessages([]);
    history.current = [];
  };

  /* Answer style for the next question; the choice is kept for the browser session. */
  const chooseStyle = (key) => {
    if (styleLocked || key === answerStyle) return;
    setAnswerStyle(key);
    saveAnswerStyle(key);
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      e.currentTarget.form.requestSubmit();
    }
  };

  /* Preview panel: single-file modes show the document straight away; multi-file modes ask the user to pick one. */
  const activeDoc = pickDocument ? selectedDoc : (files.length ? 0 : null);
  const activeFile = activeDoc != null ? files[activeDoc] : null;
  const previewTitle = activeFile ? activeFile.name : (files.length ? 'Select a document to preview' : 'Preview');
  const previewEmpty = files.length ? 'Choose a document above to see its preview.' : 'No document to preview.';

  return (
    <>
      <Waves p="ch" />

      <header className="ch-header">
        <Link aria-label="Back to upload" className="ch-back" to="/get-started">
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M11 6l-6 6 6 6" />
          </svg>
        </Link>
        <div className="ch-header__inner">
          <div className="ch-brand">
            <img alt="" className="ch-brand__logo" src="/assets/docsense-logo.png" />
            <span className="ch-brand__name">DocSense</span>
            <span aria-hidden="true" className="ch-brand__divider" />
            <span className="ch-mode">{MODE_ICONS[mode]}<span>{modeLabel}</span></span>
            <div
              aria-describedby={styleLocked ? 'ch-style-note' : undefined}
              aria-label={CHAT_CONFIG.text.styleGroup}
              className={`ch-style${styleLocked ? ' is-locked' : ''}`}
              role="group"
              style={{ '--i': Math.max(0, ANSWER_STYLES.findIndex((s) => s.key === answerStyle)) }}
              title={styleLocked ? CHAT_CONFIG.text.styleLocked : undefined}
            >
              <span aria-hidden="true" className="ch-style__thumb" />
              {ANSWER_STYLES.map((s) => (
                <button
                  key={s.key}
                  aria-pressed={answerStyle === s.key}
                  className="ch-style__opt"
                  disabled={styleLocked && s.key !== answerStyle}
                  title={styleLocked ? undefined : s.hint}
                  type="button"
                  onClick={() => chooseStyle(s.key)}
                >
                  {STYLE_ICONS[s.key]}
                  <span>{s.label}</span>
                </button>
              ))}
              {styleLocked && <span className="ch-sr" id="ch-style-note">{CHAT_CONFIG.text.styleLocked}</span>}
            </div>
          </div>
          <button
            aria-controls="ch-preview"
            aria-expanded={previewOpen}
            aria-label="Show document preview"
            className="ch-preview-toggle"
            type="button"
            onClick={() => setPreviewOpen((o) => !o)}
          >
            <DocIcon />
            <span>Preview</span>
          </button>
        </div>
      </header>

      <main className="ch-main" id="main">
        <div className="ch-clear-row">
          <button
            className="ch-clear"
            disabled={busy || !messages.length}
            title="Delete this conversation from this browser"
            type="button"
            onClick={clearChat}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 7h16M9 7V4h6v3M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M10 11v6M14 11v6" />
            </svg>
            <span>Clear chat</span>
          </button>
        </div>
        <div aria-live="polite" className="ch-thread" role="log">
          {messages.map((m) => {
            if (m.type === 'user') {
              return (
                <div className="ch-row ch-row--user" key={m.id}>
                  <div className="ch-bubble">{m.text}</div>
                  <UserAvatar />
                </div>
              );
            }
            if (m.type === 'loading') {
              return (
                <div className="ch-row" key={m.id}>
                  <AiAvatar loading />
                  <div className="ch-card">
                    <div aria-label="DocSense is answering" className="ch-typing" role="status"><i /><i /><i /></div>
                  </div>
                </div>
              );
            }
            if (m.type === 'error') {
              return (
                <div className="ch-row" key={m.id}>
                  <AiAvatar />
                  <div className="ch-card ch-card--error"><div className="ch-answer" role="alert">{m.text}</div></div>
                </div>
              );
            }
            return (
              <div className="ch-row" key={m.id}>
                <AiAvatar />
                <AnswerCard data={m.data} urlFor={urlFor} />
              </div>
            );
          })}
        </div>
      </main>

      <aside aria-label="Document preview" className="ch-preview" id="ch-preview">
        <div className="ch-preview__head">
          <DocIcon className="ch-preview__icon" />
          <h2 className="ch-preview__title" title={previewTitle}>{previewTitle}</h2>
          <button aria-label="Close preview" className="ch-preview__close" type="button" onClick={() => setPreviewOpen(false)}>
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </div>
        {pickDocument && files.length > 0 && (
          <div aria-label="Choose a document to preview" className="ch-preview__docs" role="tablist">
            {files.map((f, i) => (
              <button
                key={`${f.name}-${i}`}
                aria-selected={selectedDoc === i}
                className={`ch-doc-chip${selectedDoc === i ? ' is-active' : ''}`}
                role="tab"
                title={f.name}
                type="button"
                onClick={() => setSelectedDoc(i)}
              >
                {f.name}
              </button>
            ))}
          </div>
        )}
        <div className="ch-preview__body">
          {activeFile
            ? <iframe className="ch-preview__frame" src={`${urls[activeFile.name] || ''}#navpanes=0&view=FitH`} title="Document preview" />
            : <p className="ch-preview__empty">{previewEmpty}</p>}
        </div>
      </aside>

      <div className="ch-composer">
        <h1 className="ch-composer__title">Ask anything about your document</h1>
        <form autoComplete="off" className="ch-prompt" onSubmit={submit}>
          <button aria-label="Attach a file" className="ch-icon-btn" type="button" onClick={() => { if (!CHAT_CONFIG.attachments.enabled) showToast(CHAT_CONFIG.text.noAttach); }}>
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m21 11.5-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9" />
            </svg>
          </button>
          <label className="ch-sr" htmlFor="ch-input">Type your question</label>
          <textarea
            ref={textareaRef}
            id="ch-input"
            name="question"
            placeholder="Type your question"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button aria-label="Send question" className="ch-send" disabled={busy} type="submit">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor"><path d="M3.4 20.4 21 12 3.4 3.6l.1 6.5L15 12 3.5 13.9z" /></svg>
          </button>
        </form>
      </div>

      <div aria-live="polite" className={`ch-toast${toast.visible ? ' is-visible' : ''}`} role="status">{toast.message}</div>
    </>
  );
}
