import { Fragment } from 'react';

/**
 * Renders an AI answer as React elements (never as raw HTML). Supports paragraphs, "-" bullets,
 * "1." numbered lists, **bold** and clickable [n] citation markers.
 */
function parseBlocks(text) {
  const blocks = [];
  let para = [];
  let list = null;
  const flushPara = () => { if (para.length) { blocks.push({ type: 'p', lines: para }); para = []; } };
  const flushList = () => { if (list) { blocks.push(list); list = null; } };

  String(text).replace(/\r/g, '').split('\n').forEach((ln) => {
    const bullet = ln.match(/^\s*[-*•]\s+(.*)/);
    const numbered = ln.match(/^\s*\d+[.)]\s+(.*)/);
    if (bullet || numbered) {
      flushPara();
      const type = bullet ? 'ul' : 'ol';
      if (!list || list.type !== type) { flushList(); list = { type, items: [] }; }
      list.items.push((bullet || numbered)[1]);
    } else if (!ln.trim()) {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(ln.trim());
    }
  });
  flushPara();
  flushList();
  return blocks;
}

function Inline({ text, onCite }) {
  const parts = text.split(/(\*\*.+?\*\*|\[\d{1,3}\])/g);
  return parts.map((part, i) => {
    if (!part) return null;
    if (/^\*\*.+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    const cite = part.match(/^\[(\d{1,3})\]$/);
    if (cite) {
      return (
        <button key={i} aria-label={`Go to source ${cite[1]}`} className="ch-cite" type="button" onClick={() => onCite(Number(cite[1]))}>
          [{cite[1]}]
        </button>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export default function RichText({ text, onCite }) {
  return parseBlocks(text).map((b, i) => {
    if (b.type === 'p') {
      return (
        <p key={i}>
          {b.lines.map((line, k) => (
            <Fragment key={k}>
              {k > 0 && <br />}
              <Inline text={line} onCite={onCite} />
            </Fragment>
          ))}
        </p>
      );
    }
    const List = b.type;
    return (
      <List key={i}>
        {b.items.map((item, k) => (
          <li key={k}><Inline text={item} onCite={onCite} /></li>
        ))}
      </List>
    );
  });
}
