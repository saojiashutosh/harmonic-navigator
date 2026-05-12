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
    hindi: { emoji: "🇮🇳", title: "Hindi", desc: "Hindi melodies and Bollywood magic." },
    english: { emoji: "🎤", title: "English", desc: "English pop, rock, and everything in between." },
    marathi: { emoji: "🪘", title: "Marathi", desc: "Regional roots. Marathi soul and rhythm." },
    punjabi: { emoji: "💃", title: "Punjabi", desc: "High energy bhangra and Punjabi pop." },
    gujarati: { emoji: "🎊", title: "Gujarati", desc: "Gujarati folk and film music." },
    tamil: { emoji: "🥁", title: "Tamil", desc: "Tamil beats and Kollywood hits." },
    telugu: { emoji: "🎷", title: "Telugu", desc: "Telugu tunes and Tollywood energy." },
    no_preference: { emoji: "🌍", title: "No Preference", desc: "No boundaries. Music is universal." },
  },
  music_style: {
    no_preference: { emoji: "🎶", title: "No Preference", desc: "Open to anything. Mix it up." },
    bollywood: { emoji: "🎬", title: "Bollywood", desc: "Bollywood soundtracks and Hindi film music." },
    hollywood: { emoji: "🌟", title: "Hollywood", desc: "Hollywood scores and English pop hits." },
    marathi: { emoji: "🪘", title: "Marathi", desc: "Marathi regional music and natya sangeet." },
    devotional: { emoji: "🙏", title: "Devotional", desc: "Spiritual, bhajans and devotional music." },
    instrumental: { emoji: "🎻", title: "Instrumental", desc: "Pure instrumental. Let the music speak." },
    classical: { emoji: "🪷", title: "Classical", desc: "Indian classical ragas and timeless beauty." },
    pop: { emoji: "🎤", title: "Pop", desc: "Catchy hooks and sing-along vibes." },
    indie: { emoji: "🎸", title: "Indie", desc: "Underground, authentic, unpolished gems." },
    lofi: { emoji: "🌊", title: "Lo-Fi", desc: "Beats to relax, study, or zone out." },
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

// Render question text with the last 2 words highlighted in teal
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

const QuestionPage = ({ onRestart, onComplete, onInteraction, onGenerating }) => {
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

      if (!isMounted) return;

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

    return () => { isMounted = false; };
  }, []);

  const ensureSessionId = async () => {
    if (sessionId) return sessionId;
    const session = await createMoodSession();
    setSessionId(session.id);
    return session.id;
  };

  const handleOptionSelect = (value) => {
    const currentQ = questions[currentQuestionIndex];
    if (currentQ.inputType === 'multi_select') {
      setAnswers(prev => {
        const current = Array.isArray(prev[currentQ.key]) ? prev[currentQ.key] : [];
        const next = current.includes(value)
          ? current.filter(v => v !== value)
          : [...current, value];
        return { ...prev, [currentQ.key]: next };
      });
    } else {
      setAnswers(prev => ({ ...prev, [currentQ.key]: value }));
      setPulsingCard(value);
      setTimeout(() => setPulsingCard(null), 350);
    }
    onInteraction?.();
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
    onGenerating?.(true);
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
        tracks: playlistTracks.map(pt => ({ ...pt.track, relevanceScore: pt.relevanceScore })),
      });
      completed = true;
    } catch (err) {
      console.error('Finish failed:', err);
      setError('Something went wrong generating your playlist. Please try again.');
    } finally {
      onGenerating?.(false);
      if (!completed) {
        finishStartedRef.current = false;
        setIsSubmitting(false);
      }
    }
  };

  const handleNext = () => {
    onInteraction?.();
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
        <div className="loader-content">
          <div className="pulse-ring" />
          <h2>Getting things ready...</h2>
        </div>
      </div>
    );
  }

  if (isSubmitting) {
    return (
      <div className="question-page loading-state">
        <div className="loader-content">
          <div className="pulse-ring" />
          <h2>Creating your playlist...</h2>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="question-page loading-state">
        <div className="loader-content">
          <span style={{ fontSize: '2.5rem' }}>🎵</span>
          <h2>{error}</h2>
          <button className="btn btn-outlined" onClick={onRestart}>Return Home</button>
        </div>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="question-page loading-state">
        <h2>No questions found.</h2>
        <button className="btn btn-outlined" onClick={onRestart}>Return Home</button>
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
    <div className="question-page" role="form" aria-label="Mood assessment">
      <main className="question-main">
        {/* Progress */}
        <div className="progress-section" aria-label="Question progress">
          <div className="progress-header">
            <span className="step-label">Step {stepNumber} of {totalSteps}</span>
            <span className="category-label">{currentQ.category?.replace('_', ' ') || 'Question'}</span>
          </div>
          <div className="progress-bar" role="progressbar" aria-valuenow={progressPercent} aria-valuemin="0" aria-valuemax="100">
            <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
        </div>

        {/* Breathing transition wrapper */}
        <div
          className={`question-content ${isTransitioning ? 'fade-out' : 'fade-in'}`}
          aria-live="polite"
        >
          <h1 className="question-title">
            {renderQuestionText(currentQ.text)}
          </h1>
          {currentQ.inputType === 'multi_select' && (
            <p className="multi-select-hint">Select all that apply</p>
          )}

          <div
            className={`energy-cards cols-${colCount}`}
            style={{ gridTemplateColumns: `repeat(${colCount}, 1fr)` }}
            role={currentQ.inputType === 'multi_select' ? 'group' : 'radiogroup'}
            aria-label={currentQ.text}
          >
            {(currentQ.inputType === 'select' || currentQ.inputType === 'multi_select') && currentQ.options.map((opt, idx) => {
              const isMulti = currentQ.inputType === 'multi_select';
              const isSelected = isMulti
                ? (Array.isArray(answers[currentQ.key]) && answers[currentQ.key].includes(opt.rawValue))
                : answers[currentQ.key] === opt.rawValue;
              const isPulsing = !isMulti && pulsingCard === opt.rawValue;
              const optData = getOptionData(currentQ.key, opt.rawValue, opt.label);
              return (
                <div
                  key={idx}
                  className={`energy-card ${isSelected ? 'active' : ''} ${isPulsing ? 'pulse' : ''} ${isMulti ? 'multi-select-card' : ''}`}
                  onClick={() => handleOptionSelect(opt.rawValue)}
                  onMouseEnter={() => onInteraction?.()}
                  role={isMulti ? 'checkbox' : 'radio'}
                  aria-checked={isSelected}
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleOptionSelect(opt.rawValue); } }}
                >
                  {isMulti && (
                    <span className={`multi-check ${isSelected ? 'checked' : ''}`} aria-hidden="true">
                      {isSelected ? '✓' : ''}
                    </span>
                  )}
                  <span className="card-emoji" aria-hidden="true">{optData.emoji}</span>
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
                  aria-label="Artist name input"
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
            aria-label="Previous question"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
            Previous
          </button>

          <div className="pagination-dots" aria-hidden="true">
            {questions.map((q, idx) => (
              <span key={q.id} className={`dot ${idx === currentQuestionIndex ? 'active' : ''} ${idx < currentQuestionIndex ? 'completed' : ''}`} />
            ))}
          </div>

          <button
            className={`nav-btn next-btn ${isSubmitting ? 'submitting' : ''}`}
            onClick={handleNext}
            disabled={isSubmitting}
            aria-label={isLastQuestion ? 'Generate playlist' : 'Next question'}
          >
            {isSubmitting ? (
              <>
                <span className="btn-spinner" />
                Generating...
              </>
            ) : (
              <>
                {isLastQuestion ? 'Finish' : 'Next'}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
};

export default QuestionPage;
