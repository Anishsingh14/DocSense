
export default function HowItWorks() {
  return (
    <>
    <section className="py-16 sm:py-24 bg-section" id="how-it-works">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div className="inline-block mb-3">
          <span className="badge-pill">
            How It Works
          </span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-ink tracking-tight mb-14">
          Simple. Powerful. Accurate.
        </h2>
        <div className="relative grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 items-stretch">
          <div className="bg-card rounded-2xl p-6 border border-shade shadow-soft hover:shadow-card hover:-translate-y-1 transition-all flex flex-col items-center text-center relative group">
            <div className="w-14 h-14 rounded-full bg-shade text-ink flex items-center justify-center mb-5 shadow-sm group-hover:scale-110 group-hover:bg-ink group-hover:text-gold transition-all">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" x2="12" y1="3" y2="15" />
              </svg>
            </div>
            <h4 className="text-base font-bold text-ink mb-1">
              1. Upload
            </h4>
            <p className="text-xs text-muted font-medium">
              PDF, DOCX or TXT
            </p>
          </div>
          <div className="bg-card rounded-2xl p-6 border border-shade shadow-soft hover:shadow-card hover:-translate-y-1 transition-all flex flex-col items-center text-center relative group">
            <div className="w-14 h-14 rounded-full bg-shade text-ink flex items-center justify-center mb-5 shadow-sm group-hover:scale-110 group-hover:bg-ink group-hover:text-gold transition-all">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M12 2a4.5 4.5 0 0 0-4.5 4.5c0 1.25.51 2.38 1.34 3.19A6 6 0 0 0 4 15.5V17a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-1.5a6 6 0 0 0-4.84-5.81A4.5 4.5 0 0 0 12 2z" />
                <circle cx="12" cy="7" r="1.5" />
              </svg>
            </div>
            <h4 className="text-base font-bold text-ink mb-1">
              2. Understand
            </h4>
            <p className="text-xs text-muted font-medium">
              Analyze text and images
            </p>
          </div>
          <div className="bg-card rounded-2xl p-6 border border-shade shadow-soft hover:shadow-card hover:-translate-y-1 transition-all flex flex-col items-center text-center relative group">
            <div className="w-14 h-14 rounded-full bg-shade text-ink flex items-center justify-center mb-5 shadow-sm group-hover:scale-110 group-hover:bg-ink group-hover:text-gold transition-all">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" x2="16.65" y1="21" y2="16.65" />
              </svg>
            </div>
            <h4 className="text-base font-bold text-ink mb-1">
              3. Retrieve
            </h4>
            <p className="text-xs text-muted font-medium">
              Find relevant content
            </p>
          </div>
          <div className="bg-card rounded-2xl p-6 border border-shade shadow-soft hover:shadow-card hover:-translate-y-1 transition-all flex flex-col items-center text-center relative group">
            <div className="w-14 h-14 rounded-full bg-shade text-ink flex items-center justify-center mb-5 shadow-sm group-hover:scale-110 group-hover:bg-ink group-hover:text-gold transition-all">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" viewBox="0 0 24 24">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h4 className="text-base font-bold text-ink mb-1">
              4. Get Answers
            </h4>
            <p className="text-xs text-muted font-medium">
              With page citations
            </p>
          </div>
        </div>
      </div>
    </section>
    </>
  );
}
