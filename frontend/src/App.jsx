import React, { useState } from 'react';
import './index.css';
import QuestionPage from './components/QuestionPage';
import ResultsPage from './components/ResultsPage';
import Header from './components/Header';
import { PlayerProvider } from './components/PlayerContext';
import MusicPlayer from './components/MusicPlayer';

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [results, setResults] = useState(null);

  const handleRestart = () => {
    setResults(null);
    setCurrentView('home');
  };

  const handleComplete = (data) => {
    setResults(data);
    setCurrentView('results');
  };

  return (
    <PlayerProvider>
      <div className="home-layout relative">
        {/* Ambient background */}
        <div className="ambient-bg">
          <div className="orb orb-1"></div>
          <div className="orb orb-2"></div>
          <div className="orb orb-3"></div>
          <div className="waves-container">
            <svg className="wave-svg" viewBox="0 0 1000 100" preserveAspectRatio="none">
              <path className="wave-path wave-1" d="M0,50 C150,110 350,0 500,50 C650,100 850,0 1000,50 L1000,100 L0,100 Z" />
              <path className="wave-path wave-2" d="M0,50 C150,0 350,110 500,50 C650,0 850,110 1000,50 L1000,100 L0,100 Z" />
              <path className="wave-path wave-3" d="M0,50 C150,100 350,0 500,50 C650,100 850,0 1000,50 L1000,100 L0,100 Z" />
            </svg>
          </div>
        </div>

        {/* Shared Header */}
        <Header
          view={currentView}
          onNavigate={(view) => {
            if (view === 'home') handleRestart();
            else setCurrentView(view);
          }}
          onRestart={handleRestart}
        />

        {/* Content Area - Fixed for questions, scrollable for home/results */}
        <div className={`scrollable-content ${currentView === 'question' ? 'fixed-frame' : ''}`}>
          {currentView === 'home' && (
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

                <div className="scroll-indicator">
                  <span className="scroll-text">DEEPEN YOUR CONNECTION</span>
                  <div className="scroll-line"></div>
                </div>
              </section>

              {/* Features Section */}
              <section className="section features-section container relative z-1">
                <div className="section-header">
                  <h2 className="section-title">How it works</h2>
                  <div className="title-underline"></div>
                </div>

                <div className="features-grid">
                  {/* Card 1 */}
                  <div className="feature-card card-half">
                    <div className="card-number">01</div>
                    <h3 className="card-title">Emotional Energy</h3>
                    <p className="card-desc">
                      Answer a series of curated questions designed to sense the 
                      frequency of your current energy state.
                    </p>
                  </div>

                  {/* Card 2 */}
                  <div className="feature-card card-half relative">
                    <div className="card-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-tertiary">
                        <path d="M9 18V5l12-2v13"></path>
                        <circle cx="6" cy="18" r="3"></circle>
                        <circle cx="18" cy="16" r="3"></circle>
                      </svg>
                    </div>
                    <div className="card-number">02</div>
                    <h3 className="card-title">Personal Context</h3>
                    <p className="card-desc">
                      Provide a whisper of context. Whether it's the weather 
                      or a fleeting thought, every detail refines the harmony.
                    </p>
                  </div>

                  {/* Card 3 - Full Width */}
                  <div className="feature-card card-full">
                    <div className="card-content">
                      <div className="card-number text-secondary">03</div>
                      <h3 className="card-title">Harmonic Curation</h3>
                      <p className="card-desc">
                        Our Navigator weaves your responses into a personalized
                        auditory landscape. Receive a curated list of music that
                        resonates perfectly with who you are in this moment.
                      </p>
                      <button className="btn btn-secondary mt-auto" onClick={() => setCurrentView('question')}>BEGIN ASSESSMENT</button>
                    </div>
                    <div className="card-images">
                      <div className="image-wrapper">
                        <img src="/vibrant_pulse.png" alt="Vibrant Pulse Cover" className="card-img" />
                        <span className="img-label text-secondary">VIBRANT PULSE</span>
                      </div>
                      <div className="image-wrapper">
                        <img src="/mellow_flow.png" alt="Mellow Flow Cover" className="card-img" />
                        <span className="img-label text-tertiary">MELLOW FLOW</span>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Footer Section */}
              <footer className="footer-section text-center relative z-1">
                <h2 className="footer-title">
                  Your sound is waiting to <br />
                  be <span className="highlight-text">heard.</span>
                </h2>
                <button className="btn btn-primary btn-large flex-center mx-auto" onClick={() => setCurrentView('question')}>
                  ENTER THE NAVIGATOR <span className="arrow ml-2">→</span>
                </button>
                <p className="footer-subtitle italic">Free your mind. Let the frequencies flow.</p>
                
                <div className="footer-bottom container">
                  <span className="copyright">© 2026 HARMONIC NAVIGATOR</span>
                  <div className="footer-links">
                    <a href="#">PRIVACY</a>
                    <a href="#">TERMS</a>
                    <a href="#">SHARE MOOD</a>
                  </div>
                </div>
              </footer>
            </>
          )}

          {currentView === 'question' && (
            <QuestionPage
              onRestart={handleRestart}
              onComplete={handleComplete}
            />
          )}

          {currentView === 'results' && (
            <ResultsPage
              results={results}
              onRestart={handleRestart}
            />
          )}
        </div>

        {/* Persistent Music Player */}
        <MusicPlayer />
      </div>
    </PlayerProvider>
  );
}

export default App;
