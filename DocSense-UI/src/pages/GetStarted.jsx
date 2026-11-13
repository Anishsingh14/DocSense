import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usePage } from '../hooks/usePage';
import { useToast } from '../hooks/useToast';
import Waves from '../components/common/Waves';
import { DEFAULT_MODE, MODES, isMultiFile, modeByKey } from '../lib/modes';
import { saveSession } from '../lib/session';
import '../styles/get-started.css';

/* Upload settings: edit here. */
const SETTINGS = {
  maxFileSizeMB: 25,        // the backend's upload limit (api/service.py); 0 disables the size check
  maxFiles: 10,             // limit for the multi-file modes
  acceptedMime: ['application/pdf'],
  acceptedExt: ['.pdf'],
  messages: {
    missingFile: 'Please upload a PDF document first.',
    badType: 'Unsupported file. Please upload a PDF document.',
    tooBig: 'This file is too large. Maximum size is {max} MB.',
    tooMany: 'You can add up to {max} files.',
    onlyOne: 'This mode uses one file, so only the first one was added.',
    trimmed: 'This mode uses one file. Only “{file}” was kept.',
    ready: 'Starting {mode} with {files}…',
  },
};

const isPdf = (f) => {
  const n = f.name.toLowerCase();
  return SETTINGS.acceptedMime.includes(f.type) || SETTINGS.acceptedExt.some((e) => n.endsWith(e));
};
const fmtSize = (bytes) => (bytes < 1048576 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1048576).toFixed(1)} MB`);

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

export default function GetStarted() {
  usePage({ page: 'get-started', title: 'Upload Your PDF Document | DocSense', themeColor: '#D3D4C0' });

  const navigate = useNavigate();
  const inputRef = useRef(null);
  const dragDepth = useRef(0);
  const [files, setFiles] = useState([]);
  const [mode, setMode] = useState(DEFAULT_MODE);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [toast, showToast] = useToast(3200);

  const multi = isMultiFile(mode);

  // Stop the browser from opening a PDF that is dropped outside the drop zone.
  useEffect(() => {
    const stop = (e) => e.preventDefault();
    window.addEventListener('dragover', stop);
    window.addEventListener('drop', stop);
    return () => {
      window.removeEventListener('dragover', stop);
      window.removeEventListener('drop', stop);
    };
  }, []);

  const addFiles = (list) => {
    setError('');
    let incoming = Array.from(list || []);
    if (!incoming.length) return;
    if (!multi) {
      if (incoming.length > 1) showToast(SETTINGS.messages.onlyOne);
      incoming = incoming.slice(0, 1);
    }
    const accepted = [];
    let problem = '';
    incoming.forEach((f) => {
      if (!isPdf(f)) { problem = SETTINGS.messages.badType; return; }
      if (SETTINGS.maxFileSizeMB && f.size > SETTINGS.maxFileSizeMB * 1048576) {
        problem = SETTINGS.messages.tooBig.replace('{max}', SETTINGS.maxFileSizeMB);
        return;
      }
      accepted.push(f);
    });
    if (problem) setError(problem);
    if (!accepted.length) return;

    if (!multi) {
      setFiles([accepted[0]]);
      return;
    }
    const next = files.slice();
    for (const f of accepted) {
      if (next.some((x) => x.name === f.name && x.size === f.size)) continue; // skip duplicates
      if (next.length >= SETTINGS.maxFiles) {
        setError(SETTINGS.messages.tooMany.replace('{max}', SETTINGS.maxFiles));
        break;
      }
      next.push(f);
    }
    setFiles(next);
  };

  const removeFile = (i) => {
    setFiles((prev) => prev.filter((_, k) => k !== i));
    setError('');
  };

  const selectMode = (key) => {
    setMode(key);
    if (!isMultiFile(key) && files.length > 1) {
      showToast(SETTINGS.messages.trimmed.replace('{file}', files[0].name));
      setFiles([files[0]]);
    }
  };

  const onModeKey = (e, i) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = MODES[(i + step + MODES.length) % MODES.length];
    selectMode(next.key);
    document.getElementById(`gs-mode-${next.key}`)?.focus();
  };

  const onDrop = (e) => {
    e.preventDefault();
    dragDepth.current = 0;
    setDragOver(false);
    if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };

  const start = async () => {
    if (!files.length) {
      setError(SETTINGS.messages.missingFile);
      showToast(SETTINGS.messages.missingFile, true);
      return;
    }
    const label = modeByKey(mode).label;
    const what = files.length === 1 ? `“${files[0].name}”` : `${files.length} files`;
    showToast(SETTINGS.messages.ready.replace('{mode}', label).replace('{files}', what));

    const payload = { file: files[0], files: files.slice(), mode, modeLabel: label };
    if (typeof window.DocSenseStart === 'function') { window.DocSenseStart(payload); return; }
    await saveSession(payload);
    navigate('/chat');
  };

  const modeIndex = Math.max(0, MODES.findIndex((m) => m.key === mode));
  const hasFiles = files.length > 0;

  return (
    <>
      <Waves p="gs" />

      <Link aria-label="Back to the home page" className="gs-back" to="/#home">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M11 6l-6 6 6 6" />
        </svg>
      </Link>

      <main className="gs-main" id="main">
        <div className="gs-illustration gs-enter" style={{ '--d': '0ms' }}>
          <Link aria-label="Go to the DocSense home page" className="gs-illustration__logo" title="Home" to="/#home">
            <img alt="" height="104" src="/assets/docsense-logo.png" width="104" />
          </Link>
        </div>

        <h1 className="gs-title gs-enter" style={{ '--d': '80ms' }}>Everything You Need to Know About Your Document</h1>
        <p className="gs-subtitle gs-enter" style={{ '--d': '140ms' }}>
          Ask questions, search for information, get answers and <br className="gs-br" />
          discover important details effortlessly.
        </p>

        <section
          aria-label="PDF upload"
          className={`gs-upload gs-enter${dragOver ? ' is-dragover' : ''}${error ? ' has-error' : ''}`}
          id="gs-dropzone"
          style={{ '--d': '200ms' }}
          onDragEnter={(e) => { e.preventDefault(); dragDepth.current += 1; setDragOver(true); }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => { dragDepth.current -= 1; if (dragDepth.current <= 0) { dragDepth.current = 0; setDragOver(false); } }}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            accept="application/pdf,.pdf"
            className="gs-file-input"
            hidden
            multiple={multi}
            type="file"
            onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
          />

          {!hasFiles && (
            <div className="gs-upload__idle">
              <svg aria-hidden="true" className="gs-upload__cloud" viewBox="0 0 48 40" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 31a9 9 0 0 1-1.5-17.9A12 12 0 0 1 35 11.5 8.5 8.5 0 0 1 36 31" />
                <path d="M24 36V20M18 25l6-6 6 6" />
              </svg>
              <button className="gs-btn gs-btn--pill" type="button" onClick={() => inputRef.current?.click()}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 15V4M8 8l4-4 4 4" />
                  <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
                </svg>
                <span>Import</span>
              </button>
              <p className="gs-upload__hint">or drag &amp; drop your file here</p>
            </div>
          )}

          {hasFiles && (
            <div className="gs-upload__done">
              <ul aria-label="Selected files" className="gs-files">
                {files.map((f, i) => (
                  <li className="gs-file" key={`${f.name}-${f.size}`}>
                    <button aria-label={`Remove ${f.name}`} className="gs-file__remove" type="button" onClick={() => removeFile(i)}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round">
                        <path d="M6 6l12 12M18 6 6 18" />
                      </svg>
                    </button>
                    <svg aria-hidden="true" className="gs-file__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                      <path d="M14 3v5h5M9 13h6M9 17h4" />
                    </svg>
                    <div className="gs-file__text">
                      <p className="gs-file__name" title={f.name}>{f.name}</p>
                      <p className="gs-file__meta">{fmtSize(f.size)}</p>
                    </div>
                  </li>
                ))}
              </ul>
              {multi && files.length < SETTINGS.maxFiles && (
                <button className="gs-btn gs-btn--ghost" type="button" onClick={() => inputRef.current?.click()}>
                  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                  <span>Add more files</span>
                </button>
              )}
            </div>
          )}

          {error && <p className="gs-upload__error" role="alert">{error}</p>}
        </section>

        <div
          aria-label="Choose a mode"
          className="gs-modes gs-enter"
          id="gs-modes"
          role="radiogroup"
          style={{ '--d': '260ms', '--i': modeIndex }}
        >
          <span aria-hidden="true" className="gs-modes__indicator" />
          {MODES.map((m, i) => {
            const selected = m.key === mode;
            return (
              <button
                key={m.key}
                aria-checked={selected}
                className={`gs-mode${selected ? ' is-selected' : ''}`}
                id={`gs-mode-${m.key}`}
                role="radio"
                tabIndex={selected ? 0 : -1}
                type="button"
                onClick={() => selectMode(m.key)}
                onKeyDown={(e) => onModeKey(e, i)}
              >
                {MODE_ICONS[m.key]}
                <span>{m.label}</span>
              </button>
            );
          })}
        </div>

        <button className="gs-btn gs-btn--cta gs-enter" style={{ '--d': '320ms' }} type="button" onClick={start}>
          <span>Start</span>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </main>

      <div aria-live="polite" className={`gs-toast${toast.visible ? ' is-visible' : ''}${toast.isError ? ' is-error' : ''}`} role="status">
        {toast.message}
      </div>
    </>
  );
}
