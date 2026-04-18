import React, { useState, useEffect, useRef } from 'react';
import './QuestionPage.css';

// Full option data: emoji icon, catchy title, brief description
const OPTION_DATA = {
  energy_level: {
    drained: { emoji: "🔋", title: "A quiet hum", desc: "Soft, steady, and introspective. A low-frequency vibration." },
    low: { emoji: "🌙", title: "Running on empty", desc: "Depleted but present. Need something gentle." },
    mid: { emoji: "⚡", title: "Somewhere in between", desc: "Not high, not low. Coasting through the moment." },
    good: { emoji: "✨", title: "Electric and bright", desc: "High-voltage clarity. Sharp and ready to move." },
    charged: { emoji: "🔥", title: "Fully charged", desc: "Overflowing with energy. Bring on the intensity." },
  },
  emotional_tone: {
    happy: { emoji: "☀️", title: "Sunshine vibes", desc: "Light and warm. Everything feels just right." },
    calm: { emoji: "🧘", title: "Inner peace", desc: "Centered and still. A quiet contentment." },
    sad: { emoji: "🌧️", title: "Cloudy skies", desc: "Heavy and slow. Need something that understands." },
    tense: { emoji: "⚡", title: "On edge", desc: "Restless and wired. Mind won't settle down." },
    flat: { emoji: "😶", title: "Radio silence", desc: "Numb and flat. Not feeling much of anything." },
    excited: { emoji: "🎉", title: "Can't sit still", desc: "Buzzing with anticipation. Ready to celebrate." },
  },
  mental_state: {
    sharp: { emoji: "🎯", title: "Laser focused", desc: "Crystal clear thinking. Ready to conquer." },
    scattered: { emoji: "🌪️", title: "Mind tornado", desc: "Thoughts everywhere. Hard to pin one down." },
    drifting: { emoji: "☁️", title: "Head in the clouds", desc: "Floating away. Lost in daydreams." },
    motivated: { emoji: "🚀", title: "Ready for launch", desc: "Fired up and driven. Let's build something." },
    blank: { emoji: "📻", title: "White noise", desc: "Empty headspace. Not thinking about much." },
  },
  activity: {
    working: { emoji: "💼", title: "Grind mode", desc: "Deep in work or study. Need the right focus." },
    exercising: { emoji: "🏃", title: "Breaking a sweat", desc: "Moving and burning. Fuel the motion." },
    relaxing: { emoji: "🛋️", title: "Couch mode", desc: "Winding down. Comfort is the priority." },
    commuting: { emoji: "🚗", title: "On the move", desc: "Travelling somewhere. Soundtrack the journey." },
    social: { emoji: "🥂", title: "Party mode", desc: "With the crew. Energy and good vibes." },
    sleeping: { emoji: "😴", title: "Lights out", desc: "Drifting to sleep. Soft and slow." },
  },
  social_setting: {
    alone: { emoji: "🎧", title: "Solo session", desc: "Just you and the music. No compromises." },
    others: { emoji: "👥", title: "Crew's here", desc: "People around. Keep it universally good." },
    kids: { emoji: "👶", title: "Little ears", desc: "Kids present. Keep it clean and light." },
    meeting: { emoji: "💻", title: "Work zone", desc: "Professional setting. Background-friendly." },
  },
  music_preference: {
    lyrics: { emoji: "📝", title: "Words that hit", desc: "Lyrics to connect with. Meaning matters." },
    no_lyrics: { emoji: "🎵", title: "Pure sound", desc: "No words, just melodies. Let the music speak." },
    background: { emoji: "🔈", title: "Whisper quiet", desc: "Barely there. Ambient and unobtrusive." },
    surprise: { emoji: "🎲", title: "Dealer's choice", desc: "Surprise me. I trust the algorithm." },
  },
  music_language: {
    no_preference: { emoji: "🌍", title: "Anything goes", desc: "No boundaries. Music is universal." },
    hindi: { emoji: "🇮🇳", title: "Bollywood beats", desc: "Hindi melodies and Bollywood magic." },
    english: { emoji: "🎤", title: "English vibes", desc: "English pop, rock, and everything in between." },
    marathi: { emoji: "🪘", title: "Marathi magic", desc: "Regional roots. Marathi soul and rhythm." },
    punjabi: { emoji: "💃", title: "Punjabi energy", desc: "High energy bhangra and Punjabi pop." },
    instrumental: { emoji: "🎻", title: "No words needed", desc: "Pure instrumental. Let the instruments talk." },
  },
  music_style: {
    no_preference: { emoji: "🎶", title: "Surprise me", desc: "Open to anything. Mix it up." },
    bollywood: { emoji: "🎬", title: "Filmy feels", desc: "Bollywood soundtracks and film music." },
    hollywood: { emoji: "🌟", title: "Western pop", desc: "Hollywood scores and English pop hits." },
    pop: { emoji: "🎤", title: "Pop anthems", desc: "Catchy hooks and sing-along vibes." },
    indie: { emoji: "🎸", title: "Indie & raw", desc: "Underground, authentic, unpolished gems." },
    classical: { emoji: "🪷", title: "Classical soul", desc: "Indian classical ragas and timeless beauty." },
    raga: { emoji: "🎵", title: "Raga rhythms", desc: "Deep classical raga explorations." },
    lofi: { emoji: "🌊", title: "Lo-fi chill", desc: "Beats to relax, study, or zone out." },
    devotional: { emoji: "🙏", title: "Sacred sounds", desc: "Spiritual and devotional music." },
  },
};

const getOptionData = (questionKey, rawValue, fallbackLabel) => {
  const data = OPTION_DATA[questionKey]?.[rawValue];
  if (data) return data;
  return { emoji: "🎵", title: fallbackLabel, desc: "" };
};

// Split question text: last 2 words get the gradient treatment
const renderQuestionText = (text) => {
  const clean = text.replace(/\?$/, '');
  const words = clean.split(' ');
  if (words.length <= 2) {
    return <><span className="q-gradient">{clean}</span>?</>;
  }
  const normal = words.slice(0, -2).join(' ') + ' ';
  const highlight = words.slice(-2).join(' ');
  return (
    <>
      {normal}
      <span className="q-gradient">{highlight}</span>?
    </>
  );
};

const QuestionPage = ({ onRestart }) => {
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pulsingCard, setPulsingCard] = useState(null);
  const [isTransitioning, setIsTransitioning] = useState(false);

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
    // Trigger pulse animation
    setPulsingCard(value);
    setTimeout(() => setPulsingCard(null), 400);
  };

  const transitionTo = (nextIndex) => {
    setIsTransitioning(true);
    setTimeout(() => {
      setCurrentQuestionIndex(nextIndex);
      setIsTransitioning(false);
    }, 250);
  };

  const handleNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      transitionTo(currentQuestionIndex + 1);
    } else {
      alert("All questions answered!\n" + JSON.stringify(answers, null, 2));
    }
  };

  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      transitionTo(currentQuestionIndex - 1);
    }
  };

  if (isLoading) {
    return (
      <div className="question-page loading-state">
        <div className="ambient-bg"><div className="orb orb-1"></div><div className="orb orb-2"></div></div>
        <div className="loader-content">
          <div className="pulse-ring"></div>
          <h2>Tuning your frequency...</h2>
        </div>
      </div>
    );
  }

  if (error || questions.length === 0) {
    return (
      <div className="question-page loading-state">
        <h2>{error || "No questions found."}</h2>
        <button className="btn btn-outlined" onClick={onRestart}>RETURN TO START</button>
      </div>
    );
  }

  const currentQ = questions[currentQuestionIndex];
  const stepNumber = String(currentQuestionIndex + 1).padStart(2, '0');
  const totalSteps = String(questions.length).padStart(2, '0');
  const progressPercent = ((currentQuestionIndex + 1) / questions.length) * 100;

  const optionCount = currentQ.options?.length || 0;
  const colCount = optionCount <= 4 ? 2 : 3;

  return (
    <div className="question-page">
      {/* Ambient background */}
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

      {/* Main Content */}
      <main className="question-main">
        {/* Progress */}
        <div className="progress-section">
          <div className="progress-header">
            <span className="step-label">STEP {stepNumber} / {totalSteps}</span>
            <span className="category-label">{currentQ.category?.replace('_', ' ').toUpperCase() || 'QUESTION'}</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>

        {/* Breathing transition wrapper */}
        <div className={`question-content ${isTransitioning ? 'fade-out' : 'fade-in'}`}>
          {/* BIG Question Title */}
          <h1 className="question-title">
            {renderQuestionText(currentQ.text)}
          </h1>

          {/* Option Cards */}
          <div
            className={`energy-cards cols-${colCount}`}
            style={{ gridTemplateColumns: `repeat(${colCount}, 1fr)` }}
          >
            {currentQ.inputType === 'select' && currentQ.options.map((opt, idx) => {
              const isSelected = answers[currentQ.key] === opt.rawValue;
              const isPulsing = pulsingCard === opt.rawValue;
              const optData = getOptionData(currentQ.key, opt.rawValue, opt.label);
              return (
                <div 
                  key={idx}
                  className={`energy-card ${isSelected ? 'active' : ''} ${isPulsing ? 'pulse' : ''}`}
                  onClick={() => handleOptionSelect(opt.rawValue)}
                >
                  <span className="card-emoji">{optData.emoji}</span>
                  <h3 className="card-title-text">{optData.title}</h3>
                  {optData.desc && <p className="card-desc-text">{optData.desc}</p>}
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
               <span key={q.id} className={`dot ${idx === currentQuestionIndex ? 'active' : ''} ${idx < currentQuestionIndex ? 'completed' : ''}`} />
            ))}
          </div>

          <button className="nav-btn next-btn" onClick={handleNext}>
            {currentQuestionIndex === questions.length - 1 ? 'FINISH ' : 'NEXT QUESTION '} 
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
          </button>
        </div>
      </main>
    </div>
  );
};

export default QuestionPage;
