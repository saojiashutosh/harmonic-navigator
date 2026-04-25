import React, { useEffect, useRef, useState } from 'react';
import './QuestionPage.css';
import { fetchQuestions, createMoodSession, submitAnswers, generatePlaylist, fetchPlaylistTracks } from '../api';

// Full option data: emoji icon, catchy title, brief description
const OPTION_DATA = {
  energy_level: {
    drained: { emoji: "🔋", title: "Drained", desc: "Soft, steady, and introspective. A low-frequency vibration." },
    low: { emoji: "🌙", title: "Low Energy", desc: "Depleted but present. Need something gentle." },
    mid: { emoji: "⚡", title: "Medium Energy", desc: "Not high, not low. Coasting through the moment." },
    good: { emoji: "✨", title: "Good Energy", desc: "High-voltage clarity. Sharp and ready to move." },
    charged: { emoji: "🔥", title: "Charged", desc: "Overflowing with energy. Bring on the intensity." },
  },
  emotional_tone: {
    happy: { emoji: "☀️", title: "Happy", desc: "Light and warm. Everything feels just right." },
    calm: { emoji: "🧘", title: "Calm", desc: "Centered and still. A quiet contentment." },
    sad: { emoji: "🌧️", title: "Sad", desc: "Heavy and slow. Need something that understands." },
    tense: { emoji: "⚡", title: "Tense", desc: "Restless and wired. Mind won't settle down." },
    flat: { emoji: "😶", title: "Flat", desc: "Numb and flat. Not feeling much of anything." },
    excited: { emoji: "🎉", title: "Excited", desc: "Buzzing with anticipation. Ready to celebrate." },
  },
  mental_state: {
    sharp: { emoji: "🎯", title: "Sharp", desc: "Crystal clear thinking. Ready to conquer." },
    scattered: { emoji: "🌪️", title: "Scattered", desc: "Thoughts everywhere. Hard to pin one down." },
    drifting: { emoji: "☁️", title: "Drifting", desc: "Floating away. Lost in daydreams." },
    motivated: { emoji: "🚀", title: "Motivated", desc: "Fired up and driven. Let's build something." },
    blank: { emoji: "📻", title: "Blank", desc: "Empty headspace. Not thinking about much." },
  },
  activity: {
    working: { emoji: "💼", title: "Working", desc: "Deep in work or study. Need the right focus." },
    exercising: { emoji: "🏃", title: "Exercising", desc: "Moving and burning. Fuel the motion." },
    relaxing: { emoji: "🛋️", title: "Relaxing", desc: "Winding down. Comfort is the priority." },
    commuting: { emoji: "🚗", title: "Commuting", desc: "Travelling somewhere. Soundtrack the journey." },
    social: { emoji: "🥂", title: "Socializing", desc: "With the crew. Energy and good vibes." },
    sleeping: { emoji: "😴", title: "Sleeping", desc: "Drifting to sleep. Soft and slow." },
  },
  social_setting: {
    alone: { emoji: "🎧", title: "Alone", desc: "Just you and the music. No compromises." },
    others: { emoji: "👥", title: "With Others", desc: "People around. Keep it universally good." },
    kids: { emoji: "👶", title: "With Kids", desc: "Kids present. Keep it clean and light." },
    meeting: { emoji: "💻", title: "In a Meeting", desc: "Professional setting. Background-friendly." },
  },
  music_preference: {
    lyrics: { emoji: "📝", title: "With Lyrics", desc: "Lyrics to connect with. Meaning matters." },
    no_lyrics: { emoji: "🎵", title: "No Lyrics", desc: "No words, just melodies. Let the music speak." },
    background: { emoji: "🔈", title: "Background Music", desc: "Barely there. Ambient and unobtrusive." },
    surprise: { emoji: "🎲", title: "Surprise Me", desc: "Surprise me. I trust the algorithm." },
  },
  music_language: {
    no_preference: { emoji: "🌍", title: "No Preference", desc: "No boundaries. Music is universal." },
    hindi: { emoji: "🇮🇳", title: "Hindi", desc: "Hindi melodies and Bollywood magic." },
    english: { emoji: "🎤", title: "English", desc: "English pop, rock, and everything in between." },
    marathi: { emoji: "🪘", title: "Marathi", desc: "Regional roots. Marathi soul and rhythm." },
    punjabi: { emoji: "💃", title: "Punjabi", desc: "High energy bhangra and Punjabi pop." },
    instrumental: { emoji: "🎻", title: "Instrumental", desc: "Pure instrumental. Let the instruments talk." },
  },
  music_style: {
    no_preference: { emoji: "🎶", title: "No Preference", desc: "Open to anything. Mix it up." },
    bollywood: { emoji: "🎬", title: "Bollywood", desc: "Bollywood soundtracks and film music." },
    hollywood: { emoji: "🌟", title: "Hollywood", desc: "Hollywood scores and English pop hits." },
    pop: { emoji: "🎤", title: "Pop", desc: "Catchy hooks and sing-along vibes." },
    indie: { emoji: "🎸", title: "Indie", desc: "Underground, authentic, unpolished gems." },
    classical: { emoji: "🪷", title: "Classical", desc: "Indian classical ragas and timeless beauty." },
    raga: { emoji: "🎵", title: "Raga", desc: "Deep classical raga explorations." },
    lofi: { emoji: "🌊", title: "Lo-Fi", desc: "Beats to relax, study, or zone out." },
    devotional: { emoji: "🙏", title: "Devotional", desc: "Spiritual and devotional music." },
  },
  playlist_goal: {
    focus: { emoji: "🎯", title: "Focus", desc: "Keep me locked in and productive." },
    relax: { emoji: "🧘", title: "Relax", desc: "Help me unwind and breathe." },
    uplift: { emoji: "✨", title: "Uplift", desc: "I want something brighter and lighter." },
    escape: { emoji: "☁️", title: "Escape", desc: "Pull me into the music for a while." },
    party: { emoji: "🎉", title: "Party", desc: "Make it lively, fun, and energetic." },
    sleep: { emoji: "😴", title: "Sleep", desc: "Soft, sleepy, and peaceful." },
  },
  time_of_day: {
    morning: { emoji: "🌅", title: "Morning", desc: "Morning energy. New beginnings." },
    afternoon: { emoji: "☀️", title: "Afternoon", desc: "Cruising through the afternoon." },
    evening: { emoji: "🌆", title: "Evening", desc: "Golden hour. Day is settling." },
    late_night: { emoji: "🌙", title: "Late Night", desc: "Late night. The world is asleep." },
  },
  nostalgia_craving: {
    discover_new: { emoji: "🔮", title: "Discover New", desc: "Surprise me with something fresh." },
    old_favorites: { emoji: "💛", title: "Old Favorites", desc: "Old favourites. Songs that feel like home." },
    mix_both: { emoji: "🎲", title: "Mix Both", desc: "A mix of familiar and new discoveries." },
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

const QuestionPage = ({ onRestart, onComplete }) => {
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [pulsingCard, setPulsingCard] = useState(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const finishStartedRef = useRef(false);

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      const [questionsResult, sessionResult] = await Promise.allSettled([
        fetchQuestions(),
        createMoodSession(),
      ]);

      if (!isMounted) {
        return;
      }

      if (questionsResult.status === 'fulfilled') {
        setQuestions(questionsResult.value);
        setError(null);
      } else {
        console.error('Question init failed:', questionsResult.reason);
        setError('Could not load questions. Please try again.');
      }

      if (sessionResult.status === 'fulfilled') {
        setSessionId(sessionResult.value.id);
      } else {
        console.error('Session init failed:', sessionResult.reason);
      }

      setIsLoading(false);
    };

    init().catch((err) => {
      console.error('Init failed:', err);
      if (isMounted) {
        setError('Could not connect to the server. Please try again.');
        setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const ensureSessionId = async () => {
    if (sessionId) {
      return sessionId;
    }

    const session = await createMoodSession();
    setSessionId(session.id);
    return session.id;
  };

  const handleOptionSelect = (value) => {
    const currentQ = questions[currentQuestionIndex];
    setAnswers(prev => ({ ...prev, [currentQ.key]: value }));
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

  const handleFinish = async () => {
    if (finishStartedRef.current) return;
    finishStartedRef.current = true;
    setIsSubmitting(true);
    setError(null);
    let completed = false;
    try {
      const activeSessionId = await ensureSessionId();

      // Step 1: Submit answers
      const inference = await submitAnswers(activeSessionId, answers);

      // Step 2: Generate playlist
      const playlist = await generatePlaylist(inference.moodSessionId, 10);

      // Step 3: Fetch the actual tracks
      const playlistTracks = await fetchPlaylistTracks(playlist.id);

      // Pass everything up to App
      onComplete({
        moodLabel: inference.moodLabel,
        confidence: inference.confidence,
        rawScores: inference.rawScores,
        playlist,
        tracks: playlistTracks.map(pt => pt.track),
      });
      completed = true;
    } catch (err) {
      console.error('Finish failed:', err);
      setError('Something went wrong while generating your playlist. Please try again.');
    } finally {
      if (!completed) {
        finishStartedRef.current = false;
        setIsSubmitting(false);
      }
    }
  };

  const handleNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      transitionTo(currentQuestionIndex + 1);
    } else {
      handleFinish();
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

  if (isSubmitting) {
    return (
      <div className="question-page loading-state">
        <div className="ambient-bg"><div className="orb orb-1"></div><div className="orb orb-2"></div></div>
        <div className="loader-content">
          <div className="pulse-ring"></div>
          <h2>Generating your playlist...</h2>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="question-page loading-state">
        <div className="loader-content">
          <span style={{ fontSize: '2.5rem' }}>⚠️</span>
          <h2>{error}</h2>
          <button className="btn btn-outlined" onClick={onRestart}>RETURN TO START</button>
        </div>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="question-page loading-state">
        <h2>No questions found.</h2>
        <button className="btn btn-outlined" onClick={onRestart}>RETURN TO START</button>
      </div>
    );
  }

  const currentQ = questions[currentQuestionIndex];
  const stepNumber = String(currentQuestionIndex + 1).padStart(2, '0');
  const totalSteps = String(questions.length).padStart(2, '0');
  const progressPercent = ((currentQuestionIndex + 1) / questions.length) * 100;
  const isLastQuestion = currentQuestionIndex === questions.length - 1;

  const optionCount = currentQ.options?.length || 0;
  const colCount = optionCount <= 4 ? 2 : 3;

  return (
    <div className="question-page">
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
          <h1 className="question-title">
            {renderQuestionText(currentQ.text)}
          </h1>

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

          <button
            className={`nav-btn next-btn ${isSubmitting ? 'submitting' : ''}`}
            onClick={handleNext}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <span className="btn-spinner"></span>
                GENERATING...
              </>
            ) : (
              <>
                {isLastQuestion ? 'FINISH' : 'NEXT QUESTION'}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
};

export default QuestionPage;
