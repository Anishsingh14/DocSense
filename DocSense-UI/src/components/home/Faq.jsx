import { useState } from 'react';

const FAQS = [
  {
    q: 'Which file types are supported?',
    a: 'PDF, DOCX and TXT files. Charts and images inside your documents are read along with the text.',
  },
  {
    q: 'How do page citations work?',
    a: 'When you upload a file, it is split into passages and DocSense keeps the page number of each one. When you ask a question, the answer is written from the best-matching passages and each statement is tagged with its source. Every tag is checked against the retrieved passages and citations that cannot be verified are removed.',
  },
  {
    q: 'Can I compare multiple documents?',
    a: 'Yes. Select several documents and choose Multi-Document mode. DocSense searches every selected file and labels each part of the answer by document.',
  },
  {
    q: 'Can DocSense understand charts?',
    a: 'Yes. Charts, diagrams and figures embedded in your documents are analysed alongside the text. Scanned pages and handwriting are not currently supported.',
  },
  {
    q: 'Do I need API keys?',
    a: 'No. DocSense works out of the box, so you can upload a document and start asking questions straight away. Support for using your own API keys is planned for a future update.',
  },
];

export default function Faq() {
  const [openIndex, setOpenIndex] = useState(-1); // one item open at a time

  return (
    <section className="py-14 sm:py-20 bg-section/60 border-t border-shade/70" id="faq">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          <div className="lg:col-span-4">
            <span className="badge-pill mb-3">FAQs</span>
            <h3 className="text-3xl font-extrabold text-ink tracking-tight mb-3">
              Find answers to the common questions.
            </h3>
          </div>
          <div className="lg:col-span-8 space-y-3" data-purpose="accordion-container" id="faq-accordion">
            {FAQS.map(({ q, a }, i) => {
              const open = openIndex === i;
              return (
                <div
                  key={q}
                  className="border border-shade rounded-xl bg-card overflow-hidden transition-colors hover:border-khaki"
                >
                  <button
                    aria-controls={`faq-panel-${i + 1}`}
                    aria-expanded={open}
                    className="w-full flex items-center justify-between gap-4 p-4 text-left font-bold text-xs sm:text-sm text-ink hover:text-ink focus:outline-none"
                    id={`faq-trigger-${i + 1}`}
                    type="button"
                    onClick={() => setOpenIndex(open ? -1 : i)}
                  >
                    <span>{q}</span>
                    <svg
                      className={`w-4 h-4 shrink-0 text-ink transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
                    </svg>
                  </button>
                  <div
                    aria-labelledby={`faq-trigger-${i + 1}`}
                    className={`acc-panel ${open ? 'is-open' : ''}`}
                    id={`faq-panel-${i + 1}`}
                    role="region"
                  >
                    <div className="acc-panel-inner">
                      <p className="px-4 pb-4 text-xs text-muted leading-relaxed">{a}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
