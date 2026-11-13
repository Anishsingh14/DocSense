import { usePage } from '../hooks/usePage';
import Header from '../components/home/Header';
import Hero from '../components/home/Hero';
import ThreeQAModes from '../components/home/ThreeQAModes';
import TechnicalArchitecture from '../components/home/TechnicalArchitecture';
import EvaluationTrust from '../components/home/EvaluationTrust';
import HowItWorks from '../components/home/HowItWorks';
import About from '../components/home/About';
import Faq from '../components/home/Faq';
import Footer from '../components/home/Footer';
import BackToTop from '../components/home/BackToTop';
import '../styles/tailwind.css';
import '../styles/home-preflight.css';
import '../styles/home.css';

export default function Home() {
  usePage({
    page: 'home',
    title: 'DocSense — Ask Simply, Trace Instantly.',
    themeColor: '#F3E4C9',
  });

  return (
    <div className="home-root min-h-screen bg-section text-ink antialiased selection:bg-highlight-mark">
      <a
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:rounded-full focus:bg-card focus:px-5 focus:py-2.5 focus:text-sm focus:font-bold focus:text-espresso focus:shadow-lg"
        href="#main"
      >
        Skip to content
      </a>
      <Header />
      <main id="main">
        <Hero />
        <ThreeQAModes />
        <TechnicalArchitecture />
        <EvaluationTrust />
        <HowItWorks />
        <About />
        <Faq />
      </main>
      <Footer />
      <BackToTop />
    </div>
  );
}
