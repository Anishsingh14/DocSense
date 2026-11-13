import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { useHeroVideo } from '../../hooks/useHeroVideo';

export default function Hero() {
  const layerRef = useRef(null);
  const videoRef = useRef(null);
  useHeroVideo(layerRef, videoRef);

  return (
    <>
    <section className="relative overflow-hidden bg-page" id="home">
      <div aria-hidden="true" className="hero-video-layer absolute inset-0 z-0 overflow-hidden pointer-events-none" id="hero-video-layer" ref={layerRef}>
        <video ref={videoRef} autoPlay className="hero-video absolute inset-0 block h-full w-full object-cover" disablePictureInPicture id="hero-video" muted playsInline preload="auto" tabIndex="-1">
          <source src="/Official_Hero_section_intro.mp4" type="video/mp4" />
        </video>
      </div>
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex hero-shell flex-col justify-end pt-24 pb-12 sm:pb-14 lg:pb-12">
        <div className="max-w-2xl hero-copy">
          <span className="hero-enter delay-1 invisible inline-flex items-center gap-2 rounded-full border border-ink/20 bg-shade px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink sm:border-cream/30 sm:bg-ink sm:text-gold">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-ink sm:bg-gold" />
          </span>
          <h1 className="hero-enter delay-2 mt-5 text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.06] text-ink text-balance sm:text-gold">
            <span className="sr-only">
              DocSense —
            </span>
            Ask Simply,
            <br />
            Trace Instantly.
          </h1>
          <p className="hero-enter delay-3 mt-5 max-w-xl sm:max-w-md lg:max-w-xl text-sm sm:text-base lg:text-lg leading-relaxed text-muted sm:text-gold">
            DocSense uses AI to analyze your documents efficiently and answer any question with exact page references.
          </p>
          <div className="mt-8 hero-cta hero-enter delay-4 flex flex-col items-start sm:flex-row sm:items-center gap-3.5">
            <Link to="/get-started" className="btn btn-primary">
              <span>
                Get Started
              </span>
              {' '}
              <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" viewBox="0 0 24 24">
                <line x1="5" x2="19" y1="12" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </Link>
            {' '}
            <a className="btn btn-ghost" href="#features">
              <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                <rect height="7" width="7" x="3" y="3" rx="1.5" />
                <rect height="7" width="7" x="14" y="3" rx="1.5" />
                <rect height="7" width="7" x="14" y="14" rx="1.5" />
                <rect height="7" width="7" x="3" y="14" rx="1.5" />
              </svg>
              {' '}
              <span>
                Explore Features
              </span>
            </a>
          </div>
          <ul className="mt-8 hero-trust hero-enter delay-4 flex flex-wrap items-center gap-x-5 gap-y-2.5 text-[11px] sm:text-xs font-semibold text-ink sm:text-cream">
            <li className="flex items-center gap-2">
              <svg className="w-4 h-4 text-ink sm:text-gold" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              {' '}Secure &amp; Private
            </li>
            <li aria-hidden="true" className="hidden sm:block h-4 w-px bg-ink/25 sm:bg-cream/30" />
            <li className="flex items-center gap-2">
              <svg className="w-4 h-4 text-ink sm:text-gold" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
              {' '}AI-Powered
            </li>
            <li aria-hidden="true" className="hidden sm:block h-4 w-px bg-ink/25 sm:bg-cream/30" />
            <li className="flex items-center gap-2">
              <svg className="w-4 h-4 text-ink sm:text-gold" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="6" />
                <circle cx="12" cy="12" r="2" />
              </svg>
              {' '}Verified Citations
            </li>
          </ul>
        </div>
      </div>
    </section>
    </>
  );
}
