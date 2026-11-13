import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useHomeScroll } from '../../hooks/useHomeScroll';

const DESKTOP_NAV = [
  { id: 'home', label: 'Home' },
  { id: 'features', label: 'Features' },
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'about', label: 'About Us' },
];

const MOBILE_NAV = [
  { id: 'home', label: 'Home' },
  { id: 'features', label: 'Features' },
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'pricing', label: 'Pricing' },
  { id: 'blog', label: 'Blog' },
  { id: 'about', label: 'About Us' },
  { id: 'contact', label: 'Contact' },
];

const SPY_IDS = DESKTOP_NAV.map((n) => n.id);

function Arrow({ className, strokeWidth = 2 }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" strokeWidth={strokeWidth} viewBox="0 0 24 24">
      <line x1="5" x2="19" y1="12" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { scrolled, navHidden, activeId } = useHomeScroll(SPY_IDS);

  // Close the drawer with Escape and when the viewport becomes desktop-sized.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setMenuOpen(false); };
    const onResize = () => { if (window.innerWidth >= 1024) setMenuOpen(false); };
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', onResize);
    return () => {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', onResize);
    };
  }, []);

  const headerClass = [
    'w-full fixed inset-x-0 top-0 z-50 bg-transparent border-b border-transparent',
    scrolled && 'is-scrolled',
    navHidden && 'is-nav-hidden',
    menuOpen && 'is-menu-open',
  ].filter(Boolean).join(' ');

  return (
    <header className={headerClass} id="site-header">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-20 flex items-center justify-between gap-4">
          {/* Brand */}
          <a aria-label="DocSense home" className="flex items-center gap-2.5 group shrink-0" href="#home">
            <span
              className="site-brand-mark w-11 h-11 rounded-xl overflow-hidden flex items-center justify-center shadow-md shadow-espresso/15 group-hover:scale-105 transition-transform"
              style={{ background: '#fff' }}
            >
              <img alt="" className="h-full w-full object-contain" height="44" src="/assets/docsense-logo.png" width="44" />
            </span>
            <span className="site-brand-name text-2xl font-bold tracking-tight text-espresso font-sans">
              Doc<span className="site-brand-accent text-burgundy font-semibold">Sense</span>
            </span>
          </a>

          {/* Desktop navigation */}
          <nav aria-label="Primary" className="site-nav hidden lg:flex items-center gap-5 xl:gap-7 text-[13px] xl:text-sm font-medium text-muted">
            {DESKTOP_NAV.map(({ id, label }) => {
              const active = activeId === id;
              return (
                <a
                  key={id}
                  aria-current={active ? 'page' : undefined}
                  className={`nav-link transition-colors ${active ? 'is-active font-semibold text-ink' : 'hover:text-ink'}`}
                  href={`#${id}`}
                >
                  {label}
                </a>
              );
            })}
          </nav>

          <div className="flex items-center gap-2.5">
            <Link
              to="/get-started"
              className="site-header-cta hidden sm:inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full bg-ink text-gold text-xs lg:text-sm font-bold hover:bg-burgundy shadow-md shadow-espresso/25 transition-all hover:-translate-y-0.5"
            >
              <span>Get Started</span>
              <Arrow className="w-3.5 h-3.5" strokeWidth={2.5} />
            </Link>
            <button
              aria-controls="mobile-menu"
              aria-expanded={menuOpen}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              className="lg:hidden inline-flex items-center justify-center w-10 h-10 rounded-xl border border-shade text-ink hover:bg-shade/70 transition"
              id="mobile-menu-button"
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <svg className={`w-5 h-5 ${menuOpen ? 'hidden' : ''}`} fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" viewBox="0 0 24 24">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
              <svg className={`w-5 h-5 ${menuOpen ? '' : 'hidden'}`} fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" viewBox="0 0 24 24">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile drawer */}
      <div
        className={`lg:hidden ${menuOpen ? '' : 'hidden'} border-t border-shade bg-page max-h-[calc(100svh-5rem)] overflow-y-auto`}
        id="mobile-menu"
      >
        <nav aria-label="Mobile" className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-1">
          {MOBILE_NAV.map(({ id, label }) => (
            <a
              key={id}
              className={`mobile-nav-link ${activeId === id ? 'is-active ' : ''}flex items-center justify-between rounded-xl px-4 py-3 text-sm font-medium text-muted hover:bg-shade/70 hover:text-espresso transition`}
              href={`#${id}`}
              onClick={() => setMenuOpen(false)}
            >
              <span>{label}</span>
              <Arrow className="w-4 h-4" />
            </a>
          ))}
        </nav>
        <div className="px-4 sm:px-6 pb-5">
          <Link
            to="/get-started"
            className="flex w-full items-center justify-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-bold text-gold hover:bg-burgundy transition"
            onClick={() => setMenuOpen(false)}
          >
            <span>Get Started</span>
            <Arrow className="w-4 h-4" strokeWidth={2.5} />
          </Link>
        </div>
      </div>
    </header>
  );
}
