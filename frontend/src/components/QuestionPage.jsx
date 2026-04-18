import React, { useState } from 'react';
import './QuestionPage.css';

const QuestionPage = ({ onRestart }) => {
  const [selectedCard, setSelectedCard] = useState('electric');

  return (
    <div className="question-page">
      {/* Header */}
      <header className="header container">
        <div className="header-logo" style={{ cursor: 'pointer' }} onClick={onRestart}>Harmonic Navigator</div>
        <nav className="header-nav">
          <a href="#">Discover</a>
          <a href="#">About</a>
        </nav>
        <button className="btn btn-outlined" onClick={onRestart}>RESTART</button>
      </header>

      {/* Main Content */}
      <main className="question-main">
        {/* Progress */}
        <div className="progress-section">
          <div className="progress-header">
            <span>STEP 03 / 05</span>
            <span>CURRENT ENERGY</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill"></div>
          </div>
        </div>

        {/* Question Title */}
        <div className="question-subtitle">THE DIGITAL CURATOR</div>
        <h1 className="question-title">
          How would you describe <br />
          your <span className="italic text-tertiary" style={{marginLeft: '8px'}}>current energy?</span>
        </h1>

        {/* Option Cards */}
        <div className="energy-cards">
          {/* Card 1 */}
          <div 
            className={`energy-card ${selectedCard === 'quiet' ? 'active' : ''}`}
            onClick={() => setSelectedCard('quiet')}
          >
            <div className="card-icon-container">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 12h4l2-3 4 6 4-6 2 3h4" />
                <path d="M4 8h2l2-2 4 4 4-4 2 2h2" />
                <path d="M4 16h2l2 2 4-4 4 4 2-2h2" />
              </svg>
            </div>
            <h3 className="card-title-text">A quiet hum</h3>
            <p className="card-desc-text">Soft, steady, and introspective. A low-frequency vibration.</p>
          </div>

          {/* Card 2 */}
          <div 
            className={`energy-card ${selectedCard === 'electric' ? 'active' : ''}`}
            onClick={() => setSelectedCard('electric')}
          >
            <div className="card-icon-container">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <h3 className="card-title-text">Electric and bright</h3>
            <p className="card-desc-text">High-voltage clarity. Sharp, focused, and ready to move.</p>
          </div>

          {/* Card 3 */}
          <div 
            className={`energy-card ${selectedCard === 'slow' ? 'active' : ''}`}
            onClick={() => setSelectedCard('slow')}
          >
            <div className="card-icon-container">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="7" y="4" width="10" height="16" rx="2" ry="2" />
                <path d="M9 8h6" />
                <path d="M9 12h6" />
                <path d="M9 16h6" />
                <path d="M4 12h3" />
                <path d="M17 12h3" />
              </svg>
            </div>
            <h3 className="card-title-text">A slow, deep rhythm</h3>
            <p className="card-desc-text">Grounded and heavy. Moving with the weight of water.</p>
          </div>
        </div>

        {/* Bottom Nav */}
        <div className="bottom-nav">
          <button className="nav-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg> 
            PREVIOUS
          </button>
          <div className="pagination-dots">
            <span className="dot"></span>
            <span className="dot"></span>
            <span className="dot active"></span>
            <span className="dot"></span>
            <span className="dot"></span>
          </div>
          <button className="nav-btn">
            NEXT QUESTION 
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
          </button>
        </div>
      </main>

      {/* Footer Player */}
      <footer className="music-player-footer">
        <div className="player-content">
          <div className="now-playing">
            <div className="track-img"></div>
            <div className="track-info">
              <span className="previewing-label">PREVIEWING</span>
              <span className="track-name">Ambient Flow IV</span>
            </div>
          </div>
          
          <div className="player-controls">
            <span className="control-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><polygon points="19 20 9 12 19 4 19 20"></polygon><line x1="5" y1="19" x2="5" y2="5"></line></svg>
            </span>
            <span className="control-icon play-button">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            </span>
            <span className="control-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 4 15 12 5 20 5 4"></polygon><line x1="19" y1="5" x2="19" y2="19"></line></svg>
            </span>
          </div>

          <div className="volume-control">
            <span className="control-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
            </span>
            <div className="volume-bar">
              <div className="volume-fill"></div>
            </div>
          </div>
        </div>

        <div className="app-footer">
          <span>&copy; 2026 HARMONIC NAVIGATOR</span>
          <div className="footer-nav">
            <a href="#">PRIVACY</a>
            <a href="#">TERMS</a>
            <a href="#">SHARE MOOD</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default QuestionPage;
