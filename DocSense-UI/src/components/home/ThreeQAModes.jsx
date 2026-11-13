
export default function ThreeQAModes() {
  return (
    <>
    <section className="py-16 sm:py-24 bg-section border-t border-shade/70 scroll-mt-[-5.5rem]" id="features">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <span className="badge-pill mb-3">
          Three Q&amp;A Modes
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-ink tracking-tight mb-14">
          Choose the Mode That Fits Your Need
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
          <div className="group bg-[#FAE8EF] rounded-2xl p-7 border border-[#F3D5E1] shadow-[0_8px_30px_rgba(88,72,146,0.07)] hover:shadow-[0_12px_36px_-4px_rgba(88,72,146,0.12)] hover:-translate-y-1 transition-all flex flex-col justify-between">
            <div>
              <div className="w-12 h-12 rounded-xl bg-[#FAE8EF] text-[#C2185B] flex items-center justify-center mb-5 mx-auto group-hover:scale-110 group-hover:bg-[#880E4F] group-hover:text-[#F1EDFC] transition-all">
                <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <h4 className="mb-4 text-center text-lg font-bold text-[#C2185B]">
                General Q&amp;A
              </h4>
              <div className="text-xs sm:text-sm leading-relaxed text-[#625460]">
                <p>
                  Ask questions about a single document and get a cited answer.
                </p>
                <p className="mt-2">
                  Every answer comes with page numbers.
                </p>
              </div>
              <p className="mt-4 text-xs leading-relaxed">
                <span className="font-semibold text-[#292536]">
                  Best for :-
                </span>
                {' '}
                <span className="text-[#77717E]">
                  Manuals, Reports and Policies.
                </span>
              </p>
            </div>
          </div>
          <div className="group bg-[#E8EAF6] rounded-2xl p-7 border border-[#D5D9EE] shadow-[0_8px_30px_rgba(88,72,146,0.07)] hover:shadow-[0_12px_36px_-4px_rgba(88,72,146,0.12)] hover:-translate-y-1 transition-all flex flex-col justify-between">
            <div>
              <div className="w-12 h-12 rounded-xl bg-[#E8EAF6] text-[#3F51B5] flex items-center justify-center mb-5 mx-auto group-hover:scale-110 group-hover:bg-[#283593] group-hover:text-[#F1EDFC] transition-all">
                <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                  <path d="M9 6V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-2" />
                  <path d="M9 6l-6 5v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2H9z" />
                  <polyline points="9 6 9 11 3 11" />
                </svg>
              </div>
              <h4 className="mb-4 text-center text-lg font-bold text-[#3F51B5]">
                Multi-Document Compare
              </h4>
              <div className="text-xs sm:text-sm leading-relaxed text-[#51566B]">
                <p>
                  Compare terms and find differences across several files.
                </p>
                <p className="mt-2">
                  Every file you choose is covered and sources are labelled by document.
                </p>
              </div>
              <p className="mt-4 text-xs leading-relaxed">
                <span className="font-semibold text-[#292536]">
                  Best for :-
                </span>
                {' '}
                <span className="text-[#77717E]">
                  Comparing contracts and versions.
                </span>
              </p>
            </div>
          </div>
          <div className="group bg-[#E8F5E9] rounded-2xl p-7 border border-[#D3E8D3] shadow-[0_8px_30px_rgba(88,72,146,0.07)] hover:shadow-[0_12px_36px_-4px_rgba(88,72,146,0.12)] hover:-translate-y-1 transition-all flex flex-col justify-between">
            <div>
              <div className="w-12 h-12 rounded-xl bg-[#E8F5E9] text-[#558B2F] flex items-center justify-center mb-5 mx-auto group-hover:scale-110 group-hover:bg-[#33691E] group-hover:text-[#F1EDFC] transition-all">
                <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
                  <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
                  <path d="M7 21h10" />
                  <path d="M12 3v18" />
                  <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
                </svg>
              </div>
              <h4 className="mb-4 text-center text-lg font-bold text-[#558B2F]">
                Legal Precision Mode
              </h4>
              <div className="text-xs sm:text-sm leading-relaxed text-[#526052]">
                <p>
                  Retrieve exact clause wording, quoted as written.
                </p>
                <p className="mt-2">
                  No paraphrasing, with the page for each quote.
                </p>
              </div>
              <p className="mt-4 text-xs leading-relaxed">
                <span className="font-semibold text-[#292536]">
                  Best for :-
                </span>
                {' '}
                <span className="text-[#77717E]">
                  Exact clauses and obligations.
                </span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
    </>
  );
}
