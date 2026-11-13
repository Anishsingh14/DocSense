import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <>
    <footer className="bg-espresso text-gold border-t border-gold/15">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 lg:gap-8 py-14 sm:py-16">
          <div className="md:col-span-5 flex flex-col items-start justify-center text-left">
            <a aria-label="DocSense home" className="inline-flex items-center gap-2.5 group" href="#home">
              <span className="w-11 h-11 rounded-xl overflow-hidden flex items-center justify-center shadow-md shadow-espresso/40 group-hover:scale-105 transition-transform" style={{ background: '#fff' }}>
                <img alt="" className="h-full w-full object-contain" height="44" src="/assets/docsense-logo.png" width="44" />
              </span>
              {' '}
              <span className="text-2xl font-bold tracking-tight text-gold">
                Doc
                <span className="text-sand font-semibold">
                  Sense
                </span>
              </span>
            </a>
            <p className="mt-5 text-sm font-semibold text-gold">
              Every Answer Has a Source.
            </p>
            <p className="mt-2 max-w-xs text-xs leading-relaxed text-sand">
              Explore document-backed answers with relevant references and transparent information.
            </p>
          </div>
          <nav aria-label="Footer" className="md:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-8">
            <div>
              <h2 className="footer-heading">
                Product
              </h2>
              <ul className="mt-4 space-y-3 text-sm">
                <li>
                  <a className="footer-link" href="#features">
                    Features
                  </a>
                </li>
                <li>
                  <a className="footer-link" href="#how-it-works">
                    How It Works
                  </a>
                </li>
                <li>
                  <a className="footer-link" href="#faq">
                    FAQs
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h2 className="footer-heading">
                Company
              </h2>
              <ul className="mt-4 space-y-3 text-sm">
                <li>
                  <a className="footer-link" href="#about">
                    About Us
                  </a>
                </li>
                <li>
                  <Link to="/terms" className="footer-link">
                    Terms &amp; Conditions
                  </Link>
                </li>
              </ul>
            </div>
          </nav>
        </div>
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-gold/15 py-6 text-[11px] text-sand">
          <p>
            ©{' '}
            {new Date().getFullYear()}
            {' '}DocSense. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
    </>
  );
}
