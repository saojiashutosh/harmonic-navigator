import React from 'react';

const Header = ({ view, onNavigate, onRestart }) => {
  return (
    <header className="header container">
      <div className="header-logo" onClick={() => onNavigate('home')}>
        <img src="/logo.png" alt="Harmonic" className="logo-img" />
        <span className="logo-text">Harmonic Navigator</span>
      </div>
      
      <nav className="header-nav">
        <a href="#" className={view === 'home' ? 'active' : ''} onClick={(e) => { e.preventDefault(); onNavigate('home'); }}>Discover</a>
        <a href="#" onClick={(e) => { e.preventDefault(); }}>About</a>
      </nav>

      <div className="header-cta">
        {view === 'home' ? (
          <button className="btn btn-outlined" onClick={() => onNavigate('question')}>
            START NOW
          </button>
        ) : (
          <button className="restart-btn" onClick={onRestart}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 4v6h-6"></path>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
            </svg>
            RESTART
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;
