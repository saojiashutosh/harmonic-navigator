import React from 'react';
import './ResultsPage.css';

const MOOD_META = {
  focused:     { emoji: '🎯', label: 'Focused',     color: '#818CF8', desc: 'Sharp, clear, and ready to move forward.' },
  energized:   { emoji: '⚡', label: 'Energized',   color: '#F59E0B', desc: 'Charged up, alive, and full of momentum.' },
  calm:        { emoji: '🧘', label: 'Calm',         color: '#2DD4BF', desc: 'Grounded, still, and at ease.' },
  melancholic: { emoji: '🌧️', label: 'Melancholic', color: '#7C3AED', desc: 'Reflective, tender, and beautifully sad.' },
  anxious:     { emoji: '🌀', label: 'Anxious',      color: '#EF4444', desc: 'Restless energy that needs to breathe.' },
  celebratory: { emoji: '🎉', label: 'Celebratory', color: '#EC4899', desc: 'Joyful, bright, and ready to party.' },
};

const getMoodMeta = (label) =>
  MOOD_META[label?.toLowerCase()] ?? { emoji: '🎵', label: label ?? 'Curated', color: '#818CF8', desc: 'A sound that resonates with you.' };

const ResultsPage = ({ results, onRestart }) => {
  const { moodLabel, confidence, tracks = [] } = results ?? {};
  const meta = getMoodMeta(moodLabel);
  const confidencePct = Math.round((confidence ?? 0) * 100);

  return (
    <div className="results-page">
      {/* Ambient background */}
      <div className="ambient-bg">
        <div className="orb orb-1" style={{ '--orb-color': meta.color + '33' }}></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
        <div className="waves-container">
          <svg className="wave-svg" viewBox="0 0 1000 100" preserveAspectRatio="none">
            <path className="wave-path wave-1" d="M0,50 C150,110 350,0 500,50 C650,100 850,0 1000,50 L1000,100 L0,100 Z" />
            <path className="wave-path wave-2" d="M0,50 C150,0 350,110 500,50 C650,0 850,110 1000,50 L1000,100 L0,100 Z" />
          </svg>
        </div>
      </div>

      <div className="results-main container">
        {/* Mood Hero */}
        <div className="mood-hero">
          <div className="mood-emoji-ring" style={{ '--mood-color': meta.color }}>
            <span className="mood-emoji">{meta.emoji}</span>
          </div>
          <div className="mood-hero-text">
            <span className="results-subtitle">YOUR CURRENT RESONANCE</span>
            <h1 className="mood-title" style={{ '--mood-color': meta.color }}>
              {meta.label}
            </h1>
            <p className="mood-desc">{meta.desc}</p>
          </div>
          <div className="confidence-badge">
            <div className="confidence-ring">
              <svg viewBox="0 0 36 36" className="confidence-svg">
                <path
                  className="confidence-bg"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="confidence-fill"
                  strokeDasharray={`${confidencePct}, 100`}
                  style={{ stroke: meta.color }}
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="confidence-number">{confidencePct}%</span>
            </div>
            <span className="confidence-label">MATCH</span>
          </div>
        </div>

        {/* Divider */}
        <div className="results-divider">
          <span>YOUR CURATED PLAYLIST</span>
        </div>

        {/* Track List */}
        {tracks.length === 0 ? (
          <div className="no-tracks">
            <p>No tracks found for this mood yet. Try a different combination!</p>
            <button className="btn btn-outlined" onClick={onRestart}>TRY AGAIN</button>
          </div>
        ) : (
          <div className="tracks-grid">
            {tracks.map((track, idx) => (
              <div className="track-card" key={track?.id ?? idx}>
                <div className="track-position">{String(idx + 1).padStart(2, '0')}</div>
                <div className="track-info">
                  <h3 className="track-title">{track?.title ?? 'Unknown Track'}</h3>
                  <div className="track-meta">
                    <span className="track-mood">{track?.primaryMood ?? moodLabel}</span>
                    {track?.durationMinutes && (
                      <span className="track-duration">{track.durationMinutes}</span>
                    )}
                    {track?.language && (
                      <span className="track-lang">{track.language}</span>
                    )}
                  </div>
                </div>
                {track?.externalUrl ? (
                  <a
                    href={track.externalUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="track-play-btn"
                    title="Open in Spotify"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                    </svg>
                  </a>
                ) : (
                  <div className="track-play-btn track-play-disabled" title="No link available">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Bottom Actions */}
        <div className="results-actions">
          <button className="btn btn-outlined" onClick={onRestart}>
            START OVER
          </button>
          <a
            href={`https://open.spotify.com/search/${encodeURIComponent(meta.label + ' music')}`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            EXPLORE ON SPOTIFY
          </a>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage;
