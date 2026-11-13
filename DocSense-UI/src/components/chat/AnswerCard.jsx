import { useEffect, useRef, useState } from 'react';
import RichText from './RichText';
import { CHAT_CONFIG } from '../../lib/chatConfig';
import { styleByKey } from '../../lib/modes';

function Accordion({ label, count, open, onToggle, children }) {
  return (
    <div className={`ch-acc${open ? ' is-open' : ''}`}>
      <button aria-expanded={open} className="ch-acc__btn" type="button" onClick={onToggle}>
        <span>{label}</span>
        {count != null && <span className="ch-acc__count">{count}</span>}
        <svg className="ch-acc__chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div className="ch-acc__panel" role="region">
        <div>
          <div className="ch-acc__body">{children}</div>
        </div>
      </div>
    </div>
  );
}

function ProviderInfo({ provider }) {
  if (!provider || !provider.name) return <>{CHAT_CONFIG.text.noProvider}</>;
  const key = Object.keys(CHAT_CONFIG.providerLogos).find((k) => provider.name.toLowerCase().includes(k));
  const logo = provider.logo || (key ? CHAT_CONFIG.providerLogos[key] : '');
  return (
    <div className="ch-provider">
      {logo && <img alt={`${provider.name} logo`} src={logo} />}
      <div className="ch-provider__text">
        <div>Provider: <b>{provider.name}</b></div>
        {provider.model && <div>Model: <b>{provider.model}</b></div>}
        {provider.version && <div>Version: {provider.version}</div>}
      </div>
    </div>
  );
}

/** One AI answer: text, then independent "Sources" and "Answered by" dropdowns. */
export default function AnswerCard({ data, urlFor }) {
  const sources = Array.isArray(data.sources) ? data.sources : [];
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [providerOpen, setProviderOpen] = useState(false);
  const [flash, setFlash] = useState(null);
  const refs = useRef({});
  const timers = useRef([]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const onCite = (n) => {
    setSourcesOpen(true);
    setFlash(n);
    timers.current.push(setTimeout(() => setFlash(null), 1600));
    timers.current.push(setTimeout(() => {
      const el = refs.current[n];
      if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }, 380));
  };

  const style = styleByKey(data.style);

  return (
    <div className="ch-card">
      {style && <span className="ch-style-tag">{style.label}</span>}
      <div className="ch-answer">
        <RichText text={data.answer || ''} onCite={onCite} />
      </div>

      <Accordion label="Sources" count={sources.length || null} open={sourcesOpen} onToggle={() => setSourcesOpen((o) => !o)}>
        {!sources.length && CHAT_CONFIG.text.noSources}
        {sources.map((s, i) => {
          const n = s.index != null ? s.index : i + 1;
          const hasPage = s.page != null && s.page !== '';
          const url = hasPage ? urlFor(s.document) : '';
          return (
            <div
              key={n}
              ref={(el) => { refs.current[n] = el; }}
              className={`ch-source${flash === n ? ' is-flash' : ''}`}
            >
              <div className="ch-source__head">Source [{n}]</div>
              <dl>
                {s.document && (<><dt>Document</dt><dd>{s.document}</dd></>)}
                {s.passage && (<><dt>Passage</dt><dd><blockquote>“{s.passage}”</blockquote></dd></>)}
                {hasPage && (
                  <>
                    <dt>Page</dt>
                    <dd>
                      {url
                        ? <a href={`${url}#page=${encodeURIComponent(s.page)}`} rel="noopener noreferrer" target="_blank">{s.page}</a>
                        : s.page}
                    </dd>
                  </>
                )}
              </dl>
            </div>
          );
        })}
      </Accordion>

      <Accordion label="Answered by" open={providerOpen} onToggle={() => setProviderOpen((o) => !o)}>
        <ProviderInfo provider={data.provider} />
      </Accordion>
    </div>
  );
}
