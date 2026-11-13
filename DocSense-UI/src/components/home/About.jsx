
import Reveal from '../common/Reveal';

export default function About() {
  return (
    <>
    <section className="relative overflow-hidden py-16 sm:py-24 bg-section border-t border-shade/70" id="about">
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-stretch">
          <Reveal className="lg:col-span-5 flex flex-col justify-start gap-5">
            <div>
              <span className="badge-pill">
                About DocSense
              </span>
              <h2 className="mt-4 text-3xl sm:text-4xl font-extrabold tracking-tight text-ink text-balance">
                We build the layer between raw documents and real decisions.
              </h2>
            </div>
            <div>
              <p className="text-sm sm:text-base lg:text-lg text-muted leading-relaxed">
                DocSense started with a familiar frustration: the answer is somewhere in a 300-page file, and nobody has an afternoon to find it. We set out to make document intelligence feel less like a search box and more like a careful colleague.
              </p>
              <p className="mt-4 text-sm sm:text-base lg:text-lg text-muted leading-relaxed">
                DocSense is built for people who read contracts, policies and reports. It finds the right page, compare documents carefully, and show the source for every answer. Each answer stays linked to its page.
              </p>
            </div>
          </Reveal>
          <Reveal className="lg:col-span-7">
            <div className="space-y-3">
              <div className="rounded-2xl border border-shade bg-card/85 p-3.5 sm:p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                  Five AI providers, automatic failover
                </p>
                <ul className="mt-3 grid grid-cols-3 sm:grid-cols-5 gap-2">
                  <li className="group flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-clay bg-section/60 px-2 py-3 cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:bg-raised hover:border-solid hover:border-ink/50 hover:shadow-card">
                    <img alt="" className="h-6 w-10 object-contain transition-transform duration-300 group-hover:scale-125" src="/assets/providers/groq.svg" />
                    <span className="text-[11px] font-semibold text-muted transition-colors duration-300 group-hover:text-ink">
                      Groq
                    </span>
                  </li>
                  <li className="group flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-clay bg-section/60 px-2 py-3 cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:bg-raised hover:border-solid hover:border-ink/50 hover:shadow-card">
                    <img alt="" className="h-6 w-6 object-contain transition-transform duration-300 group-hover:scale-125" src="/assets/providers/nvidia.svg" />
                    <span className="text-[11px] font-semibold text-muted transition-colors duration-300 group-hover:text-ink">
                      NVIDIA
                    </span>
                  </li>
                  <li className="group flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-clay bg-section/60 px-2 py-3 cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:bg-raised hover:border-solid hover:border-ink/50 hover:shadow-card">
                    <img alt="" className="h-6 w-6 object-contain transition-transform duration-300 group-hover:scale-125" src="/assets/providers/cohere.svg" />
                    <span className="text-[11px] font-semibold text-muted transition-colors duration-300 group-hover:text-ink">
                      Cohere
                    </span>
                  </li>
                  <li className="group flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-clay bg-section/60 px-2 py-3 cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:bg-raised hover:border-solid hover:border-ink/50 hover:shadow-card">
                    <img alt="" className="h-6 w-6 object-contain transition-transform duration-300 group-hover:scale-125" src="/assets/providers/openrouter.svg" />
                    <span className="text-[11px] font-semibold text-muted transition-colors duration-300 group-hover:text-ink">
                      OpenRouter
                    </span>
                  </li>
                  <li className="group flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-clay bg-section/60 px-2 py-3 cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:bg-raised hover:border-solid hover:border-ink/50 hover:shadow-card">
                    <img alt="" className="h-6 w-6 object-contain transition-transform duration-300 group-hover:scale-125" src="/assets/providers/gemini.svg" />
                    <span className="text-[11px] font-semibold text-muted transition-colors duration-300 group-hover:text-ink">
                      Google Gemini
                    </span>
                  </li>
                </ul>
              </div>
              <div className="rounded-2xl border border-shade bg-card/85 p-3.5 sm:p-4">
                <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] sm:grid-rows-[auto_1fr_auto] gap-x-4 gap-y-2.5">
                  <div className="order-1 sm:order-none">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                      Step 1 · Qdrant vector search
                    </p>
                    <p className="mt-1.5 flex items-center gap-2">
                      <span className="text-3xl leading-none font-extrabold tracking-tight text-ink">
                        768
                      </span>
                      <span className="text-[11px] leading-tight text-muted">
                        dimensions per passage,
                        <br />
                        embedded with Gemini
                      </span>
                    </p>
                  </div>
                  <div className="hidden sm:block" />
                  <div className="order-5 sm:order-none mt-3 sm:mt-0">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                      Step 2 · Cross-encoder re-ranking
                    </p>
                    <p className="mt-1.5 flex items-center gap-2">
                      <span className="text-3xl leading-none font-extrabold tracking-tight text-ink">
                        Top 5
                      </span>
                      <span className="text-[11px] leading-tight text-muted">
                        passages kept after
                        <br />
                        re-scoring each one
                      </span>
                    </p>
                  </div>
                  <div className="order-2 sm:order-none flex">
                    <svg aria-label="Vector search: nearest passages around your question" className="h-full min-h-[7rem] w-full rounded-xl bg-section/70" role="img" viewBox="0 0 240 150">
                      <g stroke="rgb(var(--ds-clay))" strokeOpacity=".35" strokeWidth="1">
                        <path d="M0 50H240M0 100H240M60 0V150M120 0V150M180 0V150" />
                      </g>
                      <g fill="rgb(var(--ds-clay))">
                        <circle cx="20" cy="30" r="3" />
                        <circle cx="45" cy="115" r="3" />
                        <circle cx="60" cy="20" r="3" />
                        <circle cx="30" cy="75" r="3" />
                        <circle cx="85" cy="130" r="3" />
                        <circle cx="95" cy="40" r="3" />
                        <circle cx="150" cy="20" r="3" />
                        <circle cx="165" cy="130" r="3" />
                        <circle cx="200" cy="35" r="3" />
                        <circle cx="215" cy="85" r="3" />
                        <circle cx="200" cy="125" r="3" />
                        <circle cx="225" cy="55" r="3" />
                        <circle cx="130" cy="140" r="3" />
                        <circle cx="15" cy="130" r="3" />
                      </g>
                      <circle cx="120" cy="75" r="44" fill="rgb(var(--ds-clay))" fillOpacity=".15" stroke="rgb(var(--ds-ink))" strokeDasharray="4 4" strokeOpacity=".6" />
                      <g fill="rgb(var(--ds-ink))">
                        <circle cx="105" cy="58" r="4.5" />
                        <circle cx="140" cy="62" r="4.5" />
                        <circle cx="95" cy="88" r="4.5" />
                        <circle cx="142" cy="95" r="4.5" />
                        <circle cx="118" cy="105" r="4.5" />
                      </g>
                      <circle cx="120" cy="75" r="7" fill="#fff" stroke="rgb(var(--ds-ink))" strokeWidth="2.5" />
                      <circle cx="120" cy="75" r="2.5" fill="rgb(var(--ds-ink))" />
                    </svg>
                  </div>
                  <div aria-hidden="true" className="order-4 sm:order-none self-center justify-self-center flex h-9 w-9 items-center justify-center rounded-full bg-ink text-gold rotate-90 sm:rotate-0">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </div>
                  <div className="order-6 sm:order-none">
                    <div className="h-full rounded-xl bg-section/70 p-2.5">
                      <ol className="space-y-1.5 text-[10px] font-semibold text-muted">
                        <li className="flex items-center gap-2">
                          <span className="w-2">
                            1
                          </span>
                          <span className="h-2.5 rounded-full bg-ink" style={{ width: '92%' }} />
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-2">
                            2
                          </span>
                          <span className="h-2.5 rounded-full bg-ink/85" style={{ width: '78%' }} />
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-2">
                            3
                          </span>
                          <span className="h-2.5 rounded-full bg-ink/70" style={{ width: '65%' }} />
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-2">
                            4
                          </span>
                          <span className="h-2.5 rounded-full bg-ink/55" style={{ width: '52%' }} />
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-2">
                            5
                          </span>
                          <span className="h-2.5 rounded-full bg-ink/40" style={{ width: '42%' }} />
                        </li>
                      </ol>
                      <div className="mt-3 border-t border-dashed border-clay pt-2 flex items-center gap-1.5">
                        <span className="h-1.5 w-12 rounded-full bg-clay/50" />
                        <span className="h-1.5 w-8 rounded-full bg-clay/50" />
                        <span className="ml-auto text-[10px] italic text-muted">
                          dropped
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="order-3 sm:order-none">
                    <div className="mt-0 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted">
                      <span className="inline-flex items-center gap-1">
                        <i className="h-2 w-2 rounded-full border-2 border-ink bg-white" />
                        your question
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <i className="h-2 w-2 rounded-full bg-ink" />
                        nearest passages
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <i className="h-2 w-2 rounded-full bg-clay" />
                        other passages
                      </span>
                    </div>
                  </div>
                  <div className="hidden sm:block" />
                  <div className="order-7 sm:order-none sm:text-right">
                    <p className="text-[11px] text-muted sm:text-right">
                      Highest relevance first. The best five are kept.
                    </p>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-shade bg-card/85 p-3.5 sm:p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                    Citation accuracy
                  </p>
                  <p className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight text-ink">
                    99.2%
                  </p>
                </div>
                <div className="rounded-2xl border border-shade bg-card/85 p-3.5 sm:p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                    Median answer time
                  </p>
                  <p className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight text-ink">
                    &lt;9s
                  </p>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
    </>
  );
}