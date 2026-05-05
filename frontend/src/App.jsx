import React, { useState, useEffect, useRef, useMemo } from 'react';
import './index.css';
import { PlayerProvider, usePlayer } from './components/PlayerContext';
import MusicPlayer from './components/MusicPlayer';
import * as API from './api';
import HS from './utils/HarmonicShared';

/* ── Logo ─────────────────────────────────────────────────────── */
function HarmonicMark({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="13.2" fill="var(--paper-2)" stroke="var(--ink)" strokeWidth="0.7" opacity="0.85" />
      <path d="M5 18 Q9 13, 12 17 T18 16 T26 14" stroke="var(--accent)" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M5 21 Q10 17, 14 20 T22 19" stroke="var(--ink-soft)" strokeWidth="0.9" fill="none" strokeLinecap="round" opacity="0.55" />
      <circle cx="22" cy="11" r="1.6" fill="var(--accent)" />
    </svg>
  );
}

/* ── Tiny waveform ───────────────────────────────────────────── */
function Waveform({ energy = 0.5, width = 92, height = 24, color = 'currentColor', strokeWidth = 1.4 }) {
  const d = useMemo(() => HS.waveformPath(energy, width, height), [energy, width, height]);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={d} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" fill="none" />
    </svg>
  );
}

/* ── Botanical illustrations (one per mood) ───────────────── */
function Botanical({ mood, size = 120, color = 'var(--sage)', accent = 'var(--accent)' }) {
  const m = (mood || 'calm').toLowerCase();
  const props = { width: size, height: size, viewBox: '0 0 120 120', fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' };
  if (m === 'focused') return (
    <svg {...props}>
      <path d="M60 110 L60 30" stroke={color} strokeWidth="1.2" />
      <path d="M60 60 Q44 52, 38 38 Q52 42, 60 56 Z" fill={color} opacity="0.35" stroke={color} strokeWidth="0.8" />
      <path d="M60 50 Q76 44, 84 30 Q70 32, 60 46 Z" fill={color} opacity="0.35" stroke={color} strokeWidth="0.8" />
      <path d="M60 75 Q44 68, 36 56 Q52 60, 60 70 Z" fill={color} opacity="0.25" stroke={color} strokeWidth="0.8" />
      <circle cx="60" cy="22" r="5" fill={accent} />
    </svg>
  );
  if (m === 'energized') return (
    <svg {...props}>
      <circle cx="60" cy="60" r="9" fill={accent} />
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI * 2;
        const x1 = 60 + Math.cos(a) * 16, y1 = 60 + Math.sin(a) * 16;
        const x2 = 60 + Math.cos(a) * 36, y2 = 60 + Math.sin(a) * 36;
        return <path key={i} d={`M${x1} ${y1} Q${(x1+x2)/2 + Math.sin(a)*4} ${(y1+y2)/2 - Math.cos(a)*4}, ${x2} ${y2}`} stroke={color} strokeWidth="1.2" />;
      })}
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI * 2 + 0.4;
        const x = 60 + Math.cos(a) * 44, y = 60 + Math.sin(a) * 44;
        return <ellipse key={i} cx={x} cy={y} rx="3" ry="6" fill={color} opacity="0.4" transform={`rotate(${(a*180/Math.PI) + 90} ${x} ${y})`} />;
      })}
    </svg>
  );
  if (m === 'calm') return (
    <svg {...props}>
      <path d="M60 110 L60 50" stroke={color} strokeWidth="1" />
      <path d="M60 80 Q40 75, 30 88 Q48 88, 60 82" fill={color} opacity="0.3" stroke={color} strokeWidth="0.8" />
      <path d="M60 75 Q80 70, 90 82 Q72 82, 60 78" fill={color} opacity="0.3" stroke={color} strokeWidth="0.8" />
      <path d="M60 60 Q42 50, 28 60 Q46 60, 60 62" fill={color} opacity="0.25" stroke={color} strokeWidth="0.8" />
      <ellipse cx="60" cy="42" rx="12" ry="20" fill={color} opacity="0.45" stroke={color} strokeWidth="0.8" />
      <ellipse cx="60" cy="42" rx="3" ry="14" fill={accent} opacity="0.55" />
    </svg>
  );
  if (m === 'melancholic') return (
    <svg {...props}>
      <path d="M60 26 Q50 50, 60 70 Q70 50, 60 26 Z" fill={color} opacity="0.45" stroke={color} strokeWidth="0.9" />
      <path d="M60 70 L60 92" stroke={color} strokeWidth="1" />
      <circle cx="60" cy="22" r="2.8" fill={accent} opacity="0.7" />
      {Array.from({ length: 6 }).map((_, i) => (
        <path key={i} d={`M${40 + i * 8} 96 Q${42 + i * 8} 102, ${40 + i * 8} 108`} stroke={color} strokeWidth="1" opacity="0.5" />
      ))}
    </svg>
  );
  if (m === 'celebratory') return (
    <svg {...props}>
      <circle cx="60" cy="60" r="6" fill={accent} />
      {[14, 22, 30, 38, 46].map((r, i) => (
        <circle key={i} cx="60" cy="60" r={r} stroke={color} strokeWidth="0.9" opacity={0.7 - i * 0.1} fill="none" strokeDasharray={i % 2 ? '2 3' : 'none'} />
      ))}
      {Array.from({ length: 6 }).map((_, i) => {
        const a = (i / 6) * Math.PI * 2;
        const x = 60 + Math.cos(a) * 48, y = 60 + Math.sin(a) * 48;
        return <g key={i}>
          <circle cx={x} cy={y} r="3" fill={accent} opacity="0.7" />
          <circle cx={x + Math.cos(a + 0.4) * 6} cy={y + Math.sin(a + 0.4) * 6} r="1.5" fill={color} />
        </g>;
      })}
    </svg>
  );
  if (m === 'anxious') return (
    <svg {...props}>
      {Array.from({ length: 5 }).map((_, i) => (
        <path key={i} d={`M${30 + i * 12} 90 Q${28 + i * 12 + (i%2 ? 6 : -6)} 60, ${32 + i * 12} 30`} stroke={color} strokeWidth="1.1" opacity={0.6 - i * 0.06} fill="none" />
      ))}
      <circle cx="60" cy="32" r="4" fill={accent} opacity="0.7" />
    </svg>
  );
  // default — quiet
  return (
    <svg {...props}>
      <path d="M20 70 Q60 50, 100 70" stroke={color} strokeWidth="1.2" />
      <path d="M20 80 Q60 62, 100 80" stroke={color} strokeWidth="0.9" opacity="0.6" />
      <circle cx="60" cy="42" r="14" fill={color} opacity="0.4" stroke={color} strokeWidth="0.8" />
      <circle cx="60" cy="42" r="4" fill={accent} />
    </svg>
  );
}

/* ── Backdrop with grain + arcs ──────────────────────────── */
function PaperBackdrop() {
  return (
    <div className="og-backdrop" aria-hidden="true">
      <svg className="og-bg-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <defs>
          <filter id="ogNoise">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" />
            <feColorMatrix values="0 0 0 0 0.25  0 0 0 0 0.20  0 0 0 0 0.15  0 0 0 0.20 0" />
          </filter>
        </defs>
        <rect width="1200" height="800" fill="var(--paper)" />
        <rect width="1200" height="800" filter="url(#ogNoise)" opacity="0.5" />
        <path d="M -50 250 Q 400 200, 800 280 T 1250 240" stroke="var(--sage)" strokeWidth="1" fill="none" opacity="0.18" />
        <path d="M -50 280 Q 400 230, 800 310 T 1250 270" stroke="var(--sage)" strokeWidth="0.8" fill="none" opacity="0.12" />
        <circle cx="950" cy="180" r="120" fill="var(--accent)" opacity="0.06" />
        <circle cx="180" cy="600" r="160" fill="var(--sage)" opacity="0.05" />
      </svg>
    </div>
  );
}

/* ── Header ──────────────────────────────────────────────── */
function Header({ onHome, view }) {
  return (
    <header className="og-header">
      <button className="og-logo" onClick={onHome}>
        <HarmonicMark size={34} />
        <span>Harmonic</span>
      </button>
      <nav className="og-nav">
        <span className={view === 'home' ? 'active' : ''}>Listen</span>
        <span>Field notes</span>
        <span>About</span>
      </nav>
      <span className="og-meta">a quiet field guide · vol. i</span>
    </header>
  );
}

/* ── Landing ─────────────────────────────────────────────── */
function Landing({ onStart }) {
  return (
    <div className="og-landing">
      <div className="og-hero">
        <div className="og-hero-tag"><span className="og-hero-dot" />A field of feeling, est. 2026</div>
        <h1>
          <span>music for</span>
          <em>the weather</em>
          <span>inside.</span>
        </h1>
        <p>Tell us about the air today. We&rsquo;ll find a small handful of songs to keep you company through the next hour.</p>
        <div className="og-hero-cta">
          <button className="og-btn og-btn-primary" onClick={onStart}>
            <span>Tend to a session</span>
            <svg width="20" height="20" viewBox="0 0 20 20"><path d="M4 10 L16 10 M11 5 L16 10 L11 15" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
          <span className="og-hero-aside">~ 3 min · no account · 10 tracks</span>
        </div>
        <div className="og-hero-botanicals" aria-hidden="true">
          <Botanical mood="calm" size={88} />
          <Botanical mood="focused" size={88} />
          <Botanical mood="celebratory" size={88} />
        </div>
      </div>

      <div className="og-three">
        {[
          { n: 'one', t: 'A small conversation', d: 'Seven gentle questions, on a single page. Your words, your weather.', e: 0.3, m: 'calm' },
          { n: 'two', t: 'A reading of the room', d: 'We listen for the shape — energy, intent, the colour of the hour.', e: 0.55, m: 'focused' },
          { n: 'three', t: 'A hand-tied bouquet', d: 'Eight to ten tracks. Picked, not generated. Press play, or browse.', e: 0.85, m: 'celebratory' },
        ].map((s, i) => (
          <div key={i} className="og-step">
            <span className="og-step-num">{s.n}.</span>
            <h3>{s.t}</h3>
            <p>{s.d}</p>
            <Waveform energy={s.e} width={140} height={26} color="var(--sage)" strokeWidth={1.4} />
          </div>
        ))}
      </div>

      <div className="og-quote">
        <svg width="42" height="42" viewBox="0 0 42 42" className="og-quote-mark">
          <path d="M8 28 Q8 18, 16 16 M22 28 Q22 18, 30 16" stroke="var(--accent)" strokeWidth="2" fill="none" strokeLinecap="round" />
        </svg>
        <p>
          The best DJs don&rsquo;t play <em>songs</em>. They play <em>rooms</em> — they read what the
          evening is asking for, and they answer it.
        </p>
      </div>
    </div>
  );
}

/* ── Mood card ──────────────────────────────────────────── */
const MARGINALIA = [
  '— a small ritual',
  'no wrong answers, only honest ones',
  'change your mind freely',
  'the air today',
  '— say what is, not what should be',
  'a quiet noticing',
  'the colour of this hour',
];

function MoodCard({ onComplete }) {
  const { closePlayer } = usePlayer();
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [bleedKey, setBleedKey] = useState(null);
  const submittedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [qs, sess] = await Promise.all([API.fetchQuestions(), API.createMoodSession()]);
        if (cancelled) return;
        setQuestions(qs); setSessionId(sess.id); setLoading(false);
      } catch { if (!cancelled) { setError('Could not load.'); setLoading(false); } }
    })();
    return () => { cancelled = true; };
  }, []);

  const select = (k, v) => {
    setAnswers(p => ({ ...p, [k]: v }));
    setBleedKey(`${k}-${v}-${Date.now()}`);
  };
  const total = questions.length || 1;
  const answered = Object.keys(answers).length;
  const ready = answered >= total;

  const submit = async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    closePlayer();
    try {
      const inf = await API.submitAnswers(sessionId, answers);
      const pl = await API.generatePlaylist(inf.moodSessionId, 10);
      const tracks = await API.fetchPlaylistTracks(pl.id);
      onComplete({ moodLabel: inf.moodLabel, confidence: inf.confidence, tracks: tracks.map(t => t.track) });
    } catch (err) { setError('Failed: ' + err.message); setSubmitting(false); submittedRef.current = false; }
  };

  if (loading) return <div className="og-loading"><Waveform energy={0.3} width={140} height={28} color="var(--accent)" strokeWidth={1.6} /><p>setting the field…</p></div>;
  if (submitting) return <div className="og-loading"><Botanical mood="celebratory" size={120} /><p>tying the bouquet…</p></div>;
  if (error) return <div className="og-loading"><p>{error}</p></div>;

  return (
    <div className="og-mood">
      <aside className="og-mood-rail">
        <div className="og-rail-sticky">
          <span className="og-eyebrow">a session · {new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase()}</span>
          <h1>tell me how the<br /><em>day feels</em>.</h1>
          <p>seven small questions, on one quiet page. nothing is fixed; you can change your mind as you go.</p>
          <div className="og-rail-progress">
            <div className="og-rail-track">
              {Array.from({ length: total }).map((_, i) => (
                <span key={i} className={`og-rail-dot ${i < answered ? 'is-filled' : ''}`} />
              ))}
            </div>
            <span className="og-rail-count">{answered} of {total}</span>
          </div>
          <button className="og-btn og-btn-primary og-rail-cta" onClick={ready ? submit : undefined} disabled={!ready}>
            {ready ? 'make my bouquet →' : `${total - answered} to go`}
          </button>
          <div className="og-rail-illus" aria-hidden="true">
            <Botanical mood={answered === 0 ? 'calm' : answered < total ? 'focused' : 'celebratory'} size={150} />
          </div>
        </div>
      </aside>
      <div className="og-mood-form">
        {questions.map((q, qi) => (
          <section key={q.id} className="og-q">
            <span className="og-margin-note" aria-hidden="true">{MARGINALIA[qi % MARGINALIA.length]}</span>
            <header><span className="og-q-num">{String(qi + 1).padStart(2, '0')}</span><span className="og-q-cat">— {HS.humanize(q.category)}</span></header>
            <h2>{q.text}</h2>
            {q.inputType === 'text_input' || q.inputType === 'text' ? (
              <div className="og-text-input-wrap">
                <input
                  type="text"
                  className={`og-text-input ${answers[q.key] !== undefined ? 'is-active' : ''}`}
                  placeholder="Leave blank, or type a name..."
                  value={answers[q.key] ?? ''}
                  onChange={e => setAnswers(p => ({ ...p, [q.key]: e.target.value }))}
                />
                <button 
                  className="og-btn og-btn-ghost og-skip-btn" 
                  onClick={() => setAnswers(p => ({ ...p, [q.key]: answers[q.key] || '' }))}>
                  {answers[q.key] !== undefined ? 'entered ✓' : 'skip ↵'}
                </button>
              </div>
            ) : (
              <div className="og-options">
                {(q.options || []).map(opt => {
                  const active = answers[q.key] === opt.rawValue;
                  const bleed = bleedKey && bleedKey.startsWith(`${q.key}-${opt.rawValue}-`);
                  return (
                    <button key={opt.rawValue} className={`og-option ${active ? 'is-active' : ''} ${bleed ? 'is-bleeding' : ''}`} onClick={() => select(q.key, opt.rawValue)}>
                      <span className="og-bleed" aria-hidden="true" />
                      <div className="og-option-wave-frame">
                        <Waveform energy={HS.getEnergy(opt.rawValue)} width={80} height={26} color={active ? 'var(--accent)' : 'var(--sage)'} strokeWidth={active ? 1.6 : 1.3} />
                      </div>
                      <div className="og-option-text">
                        <span className="og-option-label">{opt.label.toLowerCase()}</span>
                        <span className="og-option-copy">{HS.copyFor(opt.rawValue).toLowerCase()}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        ))}
        <button className="og-btn og-btn-primary og-end-cta" onClick={ready ? submit : undefined} disabled={!ready}>
          {ready ? 'make my bouquet →' : `${total - answered} to go`}
        </button>
      </div>
    </div>
  );
}

/* ── Mood sigil — the hand-drawn glyph that draws itself in ─── */
function MoodSigil({ mood, drawIn = true }) {
  const m = (mood || 'calm').toLowerCase();
  const cls = `og-sigil ${drawIn ? 'is-drawing' : ''}`;
  const baseProps = { viewBox: '0 0 240 240', className: cls, 'aria-hidden': 'true' };

  const wrap = (children) => (
    <svg {...baseProps}>
      <rect width="240" height="240" fill="var(--paper-2)" rx="6" />
      <g stroke="var(--sage)" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </g>
    </svg>
  );

  if (m === 'focused') return wrap(<>
    <line className="og-stroke" x1="40" y1="120" x2="200" y2="120" pathLength="100" />
    <line className="og-stroke" x1="120" y1="40" x2="120" y2="200" pathLength="100" />
    <circle className="og-stroke" cx="120" cy="120" r="62" pathLength="100" />
    <circle className="og-stroke" cx="120" cy="120" r="32" pathLength="100" />
    <circle cx="120" cy="120" r="6" fill="var(--accent)" stroke="none" />
  </>);

  if (m === 'energized') return wrap(<>
    <circle className="og-stroke" cx="120" cy="120" r="22" pathLength="100" />
    {Array.from({ length: 12 }).map((_, i) => {
      const a = (i / 12) * Math.PI * 2;
      return <line key={i} className="og-stroke" pathLength="100"
        x1={120 + Math.cos(a) * 36} y1={120 + Math.sin(a) * 36}
        x2={120 + Math.cos(a) * 80} y2={120 + Math.sin(a) * 80} />;
    })}
    <circle cx="120" cy="120" r="9" fill="var(--accent)" stroke="none" />
  </>);

  if (m === 'calm') return wrap(<>
    <path className="og-stroke" pathLength="100" d="M 30 100 Q 120 70, 210 100" />
    <path className="og-stroke" pathLength="100" d="M 30 130 Q 120 100, 210 130" opacity="0.7" />
    <path className="og-stroke" pathLength="100" d="M 30 160 Q 120 130, 210 160" opacity="0.5" />
    <circle className="og-stroke" pathLength="100" cx="120" cy="60" r="18" />
    <circle cx="120" cy="60" r="6" fill="var(--accent)" stroke="none" opacity="0.7" />
  </>);

  if (m === 'melancholic') return wrap(<>
    <circle className="og-stroke" pathLength="100" cx="120" cy="80" r="36" />
    {Array.from({ length: 9 }).map((_, i) => (
      <line key={i} className="og-stroke" pathLength="100" x1={56 + i * 14} y1={140 + (i % 3) * 4} x2={56 + i * 14} y2={196 + (i % 3) * 4} opacity="0.6" />
    ))}
    <circle cx="120" cy="80" r="4" fill="var(--accent)" stroke="none" opacity="0.7" />
  </>);

  if (m === 'celebratory') return wrap(<>
    {[18, 32, 50, 70, 92].map((r, i) => (
      <g key={i}>
        <circle className="og-stroke" pathLength="100" cx="120" cy="120" r={r} opacity={0.85 - i * 0.13} />
        {/* Planet on the ring */}
        <g style={{ transformOrigin: '120px 120px', animation: `ogOrbit ${10 + i * 4}s linear infinite ${i % 2 === 0 ? 'normal' : 'reverse'}` }}>
          <circle cx={120 + r} cy="120" r={i === 2 ? 3.5 : 2} fill="var(--accent)" stroke="none" opacity={0.6 + i * 0.1} />
        </g>
      </g>
    ))}
    {/* Outer asteroid belt */}
    <g style={{ transformOrigin: '120px 120px', animation: 'ogOrbit 45s linear infinite' }}>
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI * 2;
        return <circle key={i} cx={120 + Math.cos(a) * 105} cy={120 + Math.sin(a) * 105} r="3" fill="var(--accent)" stroke="none" opacity="0.7" />;
      })}
    </g>
    {/* Center sun */}
    <circle cx="120" cy="120" r="8" fill="var(--accent)" stroke="none" />
  </>);

  if (m === 'anxious') return wrap(<>
    {Array.from({ length: 7 }).map((_, i) => (
      <path key={i} className="og-stroke" pathLength="100"
        d={`M${40 + i * 24} 200 Q${36 + i * 24 + (i%2 ? 12 : -12)} 120, ${44 + i * 24} 40`}
        opacity={0.7 - i * 0.05} />
    ))}
    <circle cx="120" cy="40" r="6" fill="var(--accent)" stroke="none" />
  </>);

  return wrap(<>
    <path className="og-stroke" pathLength="100" d="M 30 120 Q 60 70, 120 120 T 210 120" />
    <circle className="og-stroke" pathLength="100" cx="120" cy="120" r="60" />
  </>);
}

/* ── Results ────────────────────────────────────────────── */
function Results({ results, onRestart }) {
  const { loadPlaylist, jumpTo, isPlaying, currentTrack, queue } = usePlayer();
  const meta = HS.moodMeta(results?.moodLabel);
  const tracks = results?.tracks || [];
  const conf = Math.round((results?.confidence || 0) * 100);

  const handlePlay = (i) => {
    // If the active queue is already this set, just jump to the track
    if (queue.length > 0 && queue[0].id === tracks[0].id) {
      jumpTo(i);
    } else {
      // Otherwise, load this new bouquet into the player context
      loadPlaylist(tracks, i, results?.moodLabel, '#C26F3C');
    }
  };

  return (
    <div className="og-results">
      <div className="og-r-left">
        <div className="og-sigil-frame"><MoodSigil mood={results?.moodLabel} drawIn={true} /></div>
        <span className="og-eyebrow">your reading</span>
        <h1>{meta.label.toLowerCase()}.</h1>
        <p>{meta.desc}</p>
        <div className="og-stats">
          <div><dt>match</dt><dd>{conf}%</dd></div>
          <div><dt>tracks</dt><dd>{tracks.length}</dd></div>
          <div><dt>length</dt><dd>~{Math.round(tracks.length * 4)}m</dd></div>
        </div>
        <div className="og-r-cta">
          <button className="og-btn og-btn-primary" onClick={() => handlePlay(0)}>play the bouquet ▸</button>
          <button className="og-btn og-btn-ghost" onClick={onRestart}>start a new one</button>
        </div>
      </div>
      <div className="og-r-right">
        <div className="og-tl-head"><span>nº</span><span>track</span><span>artist</span><span>lang</span><span>time</span></div>
        {tracks.map((t, i) => {
          const active = currentTrack && currentTrack.id === t.id;
          return (
            <button key={t.id || i} className={`og-track ${active ? 'is-active' : ''}`} onClick={() => handlePlay(i)}>
              <span className="og-tr-n">{String(i + 1).padStart(2, '0')}</span>
              <span className="og-tr-t">{t.title}{active && <em> · {isPlaying ? 'playing' : 'paused'}</em>}</span>
              <span className="og-tr-a">{t.artistId?.name || t.artistName}</span>
              <span className="og-tr-l">{t.language}</span>
              <span className="og-tr-d">{t.durationMinutes}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── Player strip ──────────────────────────────────────── */
function PlayerStrip() {
  const { currentTrack: track, queue, currentIndex, isPlaying, togglePlay, playNext, playPrevious, closePlayer, moodLabel, progress, seekTo } = usePlayer();

  if (!track || !queue.length) return null;
  
  const meta = HS.moodLabel === 'anxious' ? HS.moodMeta('calm') : HS.moodMeta(moodLabel); // default to something if unknown
  const [tick, setTick] = useState(0);
  
  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => setTick(t => t + 1), 60);
    return () => clearInterval(id);
  }, [isPlaying]);

  const waveW = 220, waveH = 26, waveMid = waveH / 2, n = 44;

  const path = useMemo(() => {
    let d = '';
    for (let i = 0; i <= n; i++) {
      const x = (i / n) * waveW;
      const phase = tick / 8;
      const y = waveMid + Math.sin(i * 0.45 + phase) * 5 + Math.sin(i * 0.2 + phase * 0.7) * 3.5;
      d += (i === 0 ? 'M' : 'L') + x.toFixed(2) + ',' + y.toFixed(2) + ' ';
    }
    return d;
  }, [tick]);

  const handleSeek = (e) => {
    if (!seekTo) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    seekTo(Math.max(0, Math.min(1, x / waveW)));
  };

  const boatX = (progress || 0) * waveW;
  const boatPhase = tick / 8;
  const boatY = waveMid + Math.sin(((boatX / waveW) * n) * 0.45 + boatPhase) * 5 + Math.sin(((boatX / waveW) * n) * 0.2 + boatPhase * 0.7) * 3.5;

  return (
    <div className="og-player">
      <div className="og-player-glow" />
      <div className="og-player-inner">
        <div className="og-player-mood"><span className="og-pdot" />{(meta?.label || moodLabel || 'playing').toLowerCase()}</div>
        <div className="og-player-track">
          <span className="og-pt">{track.title}</span>
          <span className="og-pa">{track.artistId?.name || track.artistName}</span>
        </div>
        
        <svg width={waveW} height={waveH} className="og-player-wave" onClick={handleSeek} style={{ cursor: 'pointer', overflow: 'visible' }}>
          <rect width={waveW} height={waveH} fill="transparent" />
          <path d={path} stroke="var(--sage)" strokeWidth="1.2" fill="none" strokeLinecap="round" opacity="0.6" />
          <path d={path} stroke="var(--accent)" strokeWidth="1.6" fill="none" strokeLinecap="round" clipPath="url(#progress-clip)" />
          
          <clipPath id="progress-clip">
            <rect x="0" y="-10" width={boatX} height="50" />
          </clipPath>

          <g transform={`translate(${boatX}, ${boatY})`}>
            <path d="M -5 -3 L 5 -3 L 2 2 L -2 2 Z" fill="var(--accent)" />
            <path d="M 0 -3 L 0 -8 L 4 -4 L 0 -4" fill="var(--accent)" />
          </g>
        </svg>

        <div className="og-player-controls">
          <button onClick={playPrevious} disabled={currentIndex === 0}>‹‹</button>
          <button onClick={togglePlay} className="og-pp">{isPlaying ? '❚❚' : '▶'}</button>
          <button onClick={playNext} disabled={currentIndex >= queue.length - 1}>››</button>
        </div>
        <div className="og-player-meta"><span>{currentIndex + 1}/{queue.length}</span><button className="og-pclose" onClick={closePlayer}>×</button></div>
      </div>
    </div>
  );
}

/* ── Root ──────────────────────────────────────────────── */
function HarmonicOrganic({ density = 'airy', palette = 'sand', typeStyle = 'editorial' }) {
  const [view, setView] = useState('home');
  const [results, setResults] = useState(null);
  const { closePlayer } = usePlayer();

  const onComplete = (data) => { 
    setResults(data); 
    setView('results'); 
  };
  
  return (
    <div className={`og-shell density-${density} palette-${palette} type-${typeStyle}`}>
      <PaperBackdrop />
      <Header view={view} onHome={() => { setView('home'); setResults(null); }} />
      <main className={`og-main view-${view}`}>
        {view === 'home' && <Landing onStart={() => setView('mood')} />}
        {view === 'mood' && <MoodCard onComplete={onComplete} />}
        {view === 'results' && <Results results={results} onRestart={() => { setView('home'); setResults(null); }} />}
      </main>
      <PlayerStrip />
      <MusicPlayer />
    </div>
  );
}

export default function App() {
  return (
    <PlayerProvider>
      <HarmonicOrganic />
    </PlayerProvider>
  );
}
