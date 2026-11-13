
export default function TechnicalArchitecture() {
  return (
    <>
    <section className="py-14 sm:py-20 bg-section/50 border-t border-shade/70">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5">
            <span className="badge-pill mb-3">
              Under the Hood
            </span>
            <h3 className="text-3xl sm:text-4xl font-extrabold text-ink tracking-tight leading-tight mb-4">
              Precision Engine
              <br />
              for Reliable Results
            </h3>
            <p className="text-muted text-sm sm:text-base leading-relaxed mb-6">
              Our advanced RAG pipeline ensures fast, accurate and verifiable answers.
            </p>
            <a className="btn-arch" href="#how-it-works">
              <span>
                Explore Architecture
              </span>
              {' '}
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <line x1="5" x2="19" y1="12" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </a>
          </div>
          <div className="lg:col-span-7 bg-card rounded-2xl p-6 sm:p-8 border border-shade shadow-card">
            <div className="flex flex-col md:flex-row lg:flex-col xl:flex-row items-center justify-between gap-5 relative">
              <div className="flex flex-col gap-2.5 w-full md:w-auto">
                <div className="px-3.5 py-2 rounded-xl bg-section border border-shade text-xs font-bold text-ink flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-doc-pdf text-cream flex items-center justify-center text-[9px] font-black">
                    PDF
                  </span>
                  {' '}
                  <span>
                    Document.pdf
                  </span>
                </div>
                <div className="px-3.5 py-2 rounded-xl bg-section border border-shade text-xs font-bold text-ink flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-doc-docx text-cream flex items-center justify-center text-[9px] font-black">
                    DOCX
                  </span>
                  {' '}
                  <span>
                    Contract.docx
                  </span>
                </div>
                <div className="px-3.5 py-2 rounded-xl bg-section border border-shade text-xs font-bold text-ink flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-doc-txt text-cream flex items-center justify-center text-[9px] font-black">
                    TXT
                  </span>
                  {' '}
                  <span>
                    Notes.txt
                  </span>
                </div>
              </div>
              <div className="hidden md:flex lg:hidden xl:flex text-khaki">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <line x1="5" x2="19" y1="12" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </div>
              <div className="hidden lg:flex xl:hidden text-khaki" aria-hidden="true">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <line x1="12" x2="12" y1="5" y2="19" />
                  <polyline points="5 12 12 19 19 12" />
                </svg>
              </div>
              <div className="bg-ink text-gold px-6 py-6 rounded-2xl shadow-lg shadow-ink/30 text-center w-full md:w-auto min-w-[150px]">
                <div className="text-xs font-bold text-sand uppercase tracking-widest mb-1">
                  DocSense
                </div>
                <div className="text-sm font-extrabold text-gold">
                  RAG Pipeline
                </div>
              </div>
              <div className="hidden md:flex lg:hidden xl:flex text-khaki">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <line x1="5" x2="19" y1="12" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </div>
              <div className="hidden lg:flex xl:hidden text-sand" aria-hidden="true">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <line x1="12" x2="12" y1="5" y2="19" />
                  <polyline points="5 12 12 19 19 12" />
                </svg>
              </div>
              <div className="flex flex-col gap-2 w-full md:w-auto">
                <div className="px-3.5 py-1.5 rounded-lg bg-card border border-shade text-xs font-semibold text-ink flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-success" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {' '}
                  <span>
                    Gemini Embeddings
                  </span>
                </div>
                <div className="px-3.5 py-1.5 rounded-lg bg-card border border-shade text-xs font-semibold text-ink flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-success" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {' '}
                  <span>
                    Qdrant Vector DB
                  </span>
                </div>
                <div className="px-3.5 py-1.5 rounded-lg bg-card border border-shade text-xs font-semibold text-ink flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-success" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {' '}
                  <span>
                    BGE Reranker
                  </span>
                </div>
                <div className="px-3.5 py-1.5 rounded-lg bg-card border border-shade text-xs font-semibold text-ink flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-success" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {' '}
                  <span>
                    Provider Rotation
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
    </>
  );
}
