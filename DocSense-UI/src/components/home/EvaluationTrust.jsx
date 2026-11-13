
export default function EvaluationTrust() {
  return (
    <>
    <section className="py-14 sm:py-20 bg-section" id="trust">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl bg-gradient-to-r from-ink to-burgundy text-gold p-8 sm:p-12 shadow-2xl relative overflow-hidden mb-8">
          <div className="relative z-10">
            <h3 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3">
              Less Guesswork, More Clarity.
            </h3>
            <p className="text-cream text-xs sm:text-sm leading-relaxed">
              Reliable answers, verified sources and clear document insights you can count on.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <div className="group bg-card rounded-2xl p-6 border border-shade shadow-sm hover:shadow-card hover:-translate-y-1 transition-all text-center">
            <div className="w-11 h-11 rounded-full bg-shade text-ink flex items-center justify-center mb-4 mx-auto group-hover:bg-ink group-hover:text-gold transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <line x1="18" x2="18" y1="20" y2="10" />
                <line x1="12" x2="12" y1="20" y2="4" />
                <line x1="6" x2="6" y1="20" y2="14" />
              </svg>
            </div>
            <h5 className="text-sm font-bold text-ink leading-snug">
              Relevant Retrieval
            </h5>
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Finds the pages that best answer's your question, across one document or several.
            </p>
          </div>
          <div className="group bg-card rounded-2xl p-6 border border-shade shadow-sm hover:shadow-card hover:-translate-y-1 transition-all text-center">
            <div className="w-11 h-11 rounded-full bg-shade text-ink flex items-center justify-center mb-4 mx-auto group-hover:bg-ink group-hover:text-gold transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" />
                <polyline points="9 12 12 15 16 10" />
              </svg>
            </div>
            <h5 className="text-sm font-bold text-ink leading-snug">
              Quality-Controlled Deliverables
            </h5>
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Answer quality is tested against reference answers and the result gets documented.
            </p>
          </div>
          <div className="group bg-card rounded-2xl p-6 border border-shade shadow-sm hover:shadow-card hover:-translate-y-1 transition-all text-center">
            <div className="w-11 h-11 rounded-full bg-shade text-ink flex items-center justify-center mb-4 mx-auto group-hover:bg-ink group-hover:text-gold transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h5 className="text-sm font-bold text-ink leading-snug">
              Verified Citations
            </h5>
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Every citation is validated against the source text and unsupported references are removed.
            </p>
          </div>
          <div className="group bg-card rounded-2xl p-6 border border-shade shadow-sm hover:shadow-card hover:-translate-y-1 transition-all text-center">
            <div className="w-11 h-11 rounded-full bg-shade text-ink flex items-center justify-center mb-4 mx-auto group-hover:bg-ink group-hover:text-gold transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <h5 className="text-sm font-bold text-ink leading-snug">
              Resilient Processing
            </h5>
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Automatic failover across several AI providers, helps in keeping the answers available.
            </p>
          </div>
          <div className="group bg-card rounded-2xl p-6 border border-shade shadow-sm hover:shadow-card hover:-translate-y-1 transition-all text-center">
            <div className="w-11 h-11 rounded-full bg-shade text-ink flex items-center justify-center mb-4 mx-auto group-hover:bg-ink group-hover:text-gold transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <rect height="18" rx="2" ry="2" width="18" x="3" y="3" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
            </div>
            <h5 className="text-sm font-bold text-ink leading-snug">
              Visual Content Analysis
            </h5>
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Charts, diagrams and figures in the documents are interpreted alongside the text.
            </p>
          </div>
          <div className="group bg-card rounded-2xl p-6 border border-shade shadow-sm hover:shadow-card hover:-translate-y-1 transition-all text-center">
            <div className="w-11 h-11 rounded-full bg-shade text-ink flex items-center justify-center mb-4 mx-auto group-hover:bg-ink group-hover:text-gold transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h5 className="text-sm font-bold text-ink leading-snug">
              Provider Visibility
            </h5>
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Each answer is labelled with its AI provider, so you can always know, which service handled your document.
            </p>
          </div>
        </div>
      </div>
    </section>
    </>
  );
}
