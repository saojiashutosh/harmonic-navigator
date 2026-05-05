import React from 'react';

/* ── Inline SVG Logo — sound wave mark ── */
const Logo = () => (
  <svg
    width="38"
    height="38"
    viewBox="0 0 38 38"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className="logo-svg"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#5B8A8A" />
        <stop offset="100%" stopColor="#9B8EC4" />
      </linearGradient>
    </defs>
    {/* Rounded square background */}
    <rect width="38" height="38" rx="10" fill="#F5F3EF" />
    {/* Sound wave bars — 5 bars with varying heights, centered */}
    <rect x="8"  y="17" width="3" height="4"  rx="1.5" fill="url(#logoGrad)" opacity="0.5" />
    <rect x="13" y="13" width="3" height="12" rx="1.5" fill="url(#logoGrad)" opacity="0.7" />
    <rect x="18" y="9"  width="3" height="20" rx="1.5" fill="url(#logoGrad)" />
    <rect x="23" y="12" width="3" height="14" rx="1.5" fill="url(#logoGrad)" opacity="0.7" />
    <rect x="28" y="16" width="3" height="6"  rx="1.5" fill="url(#logoGrad)" opacity="0.5" />
  </svg>
);

const Header = ({ view, onNavigate, onRestart }) => {
  return (
    <header className="header container" role="navigation" aria-label="Main navigation">
      <div
        className="header-logo"
        onClick={() => onNavigate('home')}
        role="button"
        tabIndex={0}
        aria-label="Go to home page"
        onKeyDown={(e) => { if (e.key === 'Enter') onNavigate('home'); }}
      >
        <Logo />
        <span className="logo-text">Harmonic Navigator</span>
      </div>

      <nav className="header-nav" aria-label="Page navigation">
        <a
          href="#"
          className={view === 'home' ? 'active' : ''}
          onClick={(e) => { e.preventDefault(); onNavigate('home'); }}
        >
          Discover
        </a>
        <a href="#" onClick={(e) => e.preventDefault()}>About</a>
      </nav>

      <div className="header-cta">
        {view === 'home' ? (
          <button className="btn btn-primary" onClick={() => onNavigate('question')}>
            Start Now
          </button>
        ) : (
          <button
            className="restart-btn"
            onClick={onRestart}
            aria-label="Start over"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 4v6h-6" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Start Over
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;
