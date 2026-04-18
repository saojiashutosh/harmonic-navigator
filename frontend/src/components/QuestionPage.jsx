import React, { useState, useEffect } from 'react';
import './QuestionPage.css';

// Creative frontend labels mapped by question key → rawValue
const CREATIVE_LABELS = {
  energy_level: {
    drained: "🔋 Running on fumes",
    low: "🌙 Barely flickering",
    mid: "⚡ Coasting along",
    good: "✨ Feeling alive",
    charged: "🔥 Overflowing energy",
  },
  emotional_tone: {
    happy: "☀️ Sunshine vibes",
    calm: "🧘 Inner peace mode",
    sad: "🌧️ Cloudy skies",
    tense: "⚡ Wired & restless",
    flat: "😶 Radio silence",
    excited: "🎉 Can't sit still",
  },
  mental_state: {
    sharp: "🎯 Laser focused",
    scattered: "🌪️ Mind tornado",
    drifting: "☁️ Head in the clouds",
    motivated: "🚀 Ready for launch",
    blank: "📻 White noise",
  },
  activity: {
    working: "💼 Grind mode",
    exercising: "🏃 Breaking a sweat",
    relaxing: "🛋️ Couch potato life",
    commuting: "🚗 On the move",
    social: "🥂 Party mode",
    sleeping: "😴 Lights out soon",
  },
  social_setting: {
    alone: "🎧 Solo session",
    others: "👥 Crew's here",
    kids: "👶 Little ears around",
    meeting: "💻 Work zone",
  },
  music_preference: {
    lyrics: "📝 Words that hit deep",
    no_lyrics: "🎵 Pure instrumentals",
    background: "🔈 Whisper quiet",
    surprise: "🎲 Dealer's choice",
  },
  music_language: {
    no_preference: "🌍 Anything goes",
    hindi: "🇮🇳 Bollywood beats",
    english: "🎤 English vibes",
    marathi: "🪘 Marathi magic",
    punjabi: "💃 Punjabi energy",
    instrumental: "🎻 No words needed",
  },
  music_style: {
    no_preference: "🎶 Surprise me",
    bollywood: "🎬 Filmy feels",
    hollywood: "🌟 Western pop",
    pop: "🎤 Pop anthems",
    indie: "🎸 Indie & raw",
    classical: "🪷 Classical soul",
    raga: "🎵 Raga rhythms",
    lofi: "🌊 Lo-fi chill",
    devotional: "🙏 Sacred sounds",
  },
};

const getCreativeLabel = (questionKey, rawValue, fallbackLabel) => {
  return CREATIVE_LABELS[questionKey]?.[rawValue] || fallbackLabel;
};

const QuestionPage = ({ onRestart }) => {
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/moods/questions/')
      .then(res => res.json())
      .then(data => {
        if (data && data.results) {
          setQuestions(data.results);
        } else if (Array.isArray(data)) {
          setQuestions(data);
        } else {
          setQuestions([]);
        }
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to load questions:', err);
        setError('Failed to load questions.');
        setIsLoading(false);
      });
  }, []);

  const handleOptionSelect = (value) => {
    const currentQ = questions[currentQuestionIndex];
    setAnswers(prev => ({ ...prev, [currentQ.key]: value }));
  };

  const handleNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    } else {
      alert("All questions answered! Payload:\n" + JSON.stringify(answers, null, 2));
    }
  };

  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    }
  };

  if (isLoading) {
    return (
      <div className="question-page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'white' }}>
        <h2 style={{fontFamily: 'var(--font-headline)'}}>Loading the Navigator...</h2>
      </div>
    );
  }

  if (error || questions.length === 0) {
    return (
      <div className="question-page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'white', flexDirection: 'column' }}>
        <h2 style={{fontFamily: 'var(--font-headline)', marginBottom: '1rem'}}>{error || "No questions found."}</h2>
        <button className="btn btn-outlined" onClick={onRestart}>RETURN TO START</button>
      </div>
    );
  }

  const currentQ = questions[currentQuestionIndex];
  const stepNumber = String(currentQuestionIndex + 1).padStart(2, '0');
  const totalSteps = String(questions.length).padStart(2, '0');
  const progressPercent = ((currentQuestionIndex + 1) / questions.length) * 100;

  // Determine grid column count based on option count
  const optionCount = currentQ.options?.length || 0;
  const colCount = optionCount <= 4 ? 2 : 3;

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
            <span>STEP {stepNumber} / {totalSteps}</span>
            <span>{currentQ.category?.replace('_', ' ').toUpperCase() || 'QUESTION'}</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progressPercent}%`, transition: 'width 0.3s ease' }}></div>
          </div>
        </div>

        {/* Question Title */}
        <div className="question-subtitle">THE DIGITAL CURATOR</div>
        <h1 className="question-title">
          {currentQ.text}
        </h1>

        {/* Option Cards */}
        <div
          className="energy-cards"
          style={{ gridTemplateColumns: `repeat(${colCount}, 1fr)` }}
        >
          {currentQ.inputType === 'select' && currentQ.options.map((opt, idx) => {
            const isSelected = answers[currentQ.key] === opt.rawValue;
            const displayLabel = getCreativeLabel(currentQ.key, opt.rawValue, opt.label);
            return (
              <div 
                key={idx}
                className={`energy-card ${isSelected ? 'active' : ''}`}
                onClick={() => handleOptionSelect(opt.rawValue)}
              >
                <h3 className="card-title-text">{displayLabel}</h3>
              </div>
            );
          })}

          {currentQ.inputType === 'text' && (
            <div className="text-input-container" style={{ gridColumn: '1 / -1' }}>
               <input 
                 type="text" 
                 className="mood-text-input"
                 placeholder="Type an artist name... or leave blank"
                 value={answers[currentQ.key] || ''}
                 onChange={(e) => handleOptionSelect(e.target.value)}
                 autoFocus
               />
            </div>
          )}
        </div>

        {/* Bottom Nav */}
        <div className="bottom-nav">
          <button 
            className="nav-btn" 
            onClick={handlePrevious} 
            style={{ visibility: currentQuestionIndex === 0 ? 'hidden' : 'visible' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg> 
            PREVIOUS
          </button>
          
          <div className="pagination-dots">
            {questions.map((q, idx) => (
               <span key={q.id} className={`dot ${idx === currentQuestionIndex ? 'active' : ''}`} />
            ))}
          </div>

          <button className="nav-btn" onClick={handleNext}>
            {currentQuestionIndex === questions.length - 1 ? 'FINISH ' : 'NEXT QUESTION '} 
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
          </button>
        </div>
      </main>

    </div>
  );
};

export default QuestionPage;
