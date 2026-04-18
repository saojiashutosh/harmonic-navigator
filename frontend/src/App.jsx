import React, { useState } from 'react';
import './index.css';
import QuestionPage from './components/QuestionPage';
import Header from './components/Header';

function App() {
  const [currentView, setCurrentView] = useState('home');

  const handleRestart = () => {
    // Force a re-mount of QuestionPage to reset its internal state
    setCurrentView('home'); 
    setTimeout(() => setCurrentView('question'), 10);
  };

  return (
    <div className="home-layout relative">
       {/* Ambient background orbs */}
      <div className="ambient-bg">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
        
        {/* Animated Waves */}
        <div className="waves-container">
          <svg className="wave-svg" viewBox="0 0 1000 100" preserveAspectRatio="none">
            <path className="wave-path wave-1" d="M0,50 C150,110 350,0 500,50 C650,100 850,0 1000,50 L1000,100 L0,100 Z" />
            <path className="wave-path wave-2" d="M0,50 C150,0 350,110 500,50 C650,0 850,110 1000,50 L1000,100 L0,100 Z" />
            <path className="wave-path wave-3" d="M0,50 C150,100 350,0 500,50 C650,100 850,0 1000,50 L1000,100 L0,100 Z" />
          </svg>
        </div>
      </div>

      <Header 
        view={currentView} 
        onNavigate={setCurrentView} 
        onRestart={handleRestart}
      />

      {currentView === 'home' ? (
        <>
          {/* Hero Section */}
          <section className="section hero-section container text-center relative z-1">
            <span className="subtitle">THE DIGITAL CURATOR</span>
            <h1 className="hero-title">
              Discover the <br />
              Sound of Your <br />
              <span className="highlight-text">current state</span>
            </h1>
            <p className="hero-description">
              An ethereal bridge between your inner resonance and the infinite world<br />
              of sound. Let us guide you through the symphony of your emotions.
            </p>
            
            <div className="hero-buttons">
              <button className="btn btn-primary" onClick={() => setCurrentView('question')}>START YOUR JOURNEY</button>
              <button className="btn btn-outlined">EXPLORE MOODS</button>
            </div>
          </section>

          {/* Features Section */}
          <section className="section features-section container relative z-1">
            <div className="features-grid">
              <div className="feature-card">
                <div className="feature-icon">✨</div>
                <h3>Ethereal Curation</h3>
                <p>Advanced AI that understands the subtle nuances of your current vibe.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">🌊</div>
                <h3>Sonic Waves</h3>
                <p>Experience music that flows perfectly with your emotional rhythm.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">🌓</div>
                <h3>Mood Tracking</h3>
                <p>Observe your emotional journey through personalized soundscapes.</p>
              </div>
            </div>
          </section>
        </>
      ) : (
        <QuestionPage onRestart={() => setCurrentView('home')} />
      )}
    </div>
  );
}

export default App;
