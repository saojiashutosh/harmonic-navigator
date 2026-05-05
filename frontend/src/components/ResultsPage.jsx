import React from 'react';
import { usePlayer } from './PlayerContext';
import './ResultsPage.css';

const MOOD_META = {
  focused:     { emoji: '🎯', label: 'Focused',     color: '#5B8A8A', desc: 'Sharp, clear, and ready to move forward.' },
  energized:   { emoji: '⚡', label: 'Energized',   color: '#C4A882', desc: 'Charged up, alive, and full of momentum.' },
  calm:        { emoji: '🧘', label: 'Calm',         color: '#7CAE7A', desc: 'Grounded, still, and at ease.' },
  melancholic: { emoji: '🌧️', label: 'Melancholic', color: '#9B8EC4', desc: 'Reflective, tender, and beautifully sad.' },
  anxious:     { emoji: '🌀', label: 'Anxious',      color: '#C47A7A', desc: 'Restless energy that needs to breathe.' },
  celebratory: { emoji: '🎉', label: 'Celebratory', color: '#C4A882', desc: 'Joyful, bright, and ready to celebrate.' },
};

const getMoodMeta = (label) =>
  MOOD_META[label?.toLowerCase()] ?? { emoji: '🎵', label: label ?? 'Curated', color: '#5B8A8A', desc: 'A sound that resonates with you.' };

const ResultsPage = ({ results, onRestart, onInteraction }) => {
  const { moodLabel, confidence, tracks = [] } = results ?? {};
  const meta = getMoodMeta(moodLabel);
  const confidencePct = Math.round((confidence ?? 0) * 100);
  const player = usePlayer();

  const handlePlayAll = () => {
    if (tracks.length > 0) {
      player.loadPlaylist(tracks, 0, meta.label, meta.color);
    }
  };

  const handlePlayTrack = (idx) => {
    onInteraction?.();
    if (tracks.length > 0) {
      player.loadPlaylist(tracks, idx, meta.label, meta.color);
    }
  };

  return (
    <div className="results-page">
      <div className="results-main container">
        {/* Mood Hero */}
        <div className="mood-hero">
          <div className="mood-emoji-ring" style={{ '--mood-color': meta.color }}>
            <span className="mood-emoji" aria-hidden="true">{meta.emoji}</span>
          </div>
          <div className="mood-hero-text">
            <span className="results-subtitle">Your Current Resonance</span>
            <h1 className="mood-title" style={{ '--mood-color': meta.color }}>
              {meta.label}
            </h1>
            <p className="mood-desc">{meta.desc}</p>
          </div>
          <div className="confidence-badge" aria-label={`${confidencePct}% match confidence`}>
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
            <span className="confidence-label">Match</span>
          </div>
        </div>

        {/* Divider */}
        <div className="results-divider">
          <span>Your Curated Playlist</span>
        </div>

        {/* Play All */}
        {tracks.length > 0 && (() => {
          const isPlaylistActive = player.hasQueue
            && player.currentTrack?.id === tracks[player.currentIndex]?.id;

          return (
            <div className="play-all-container">
              <button
                className={`btn-play-all ${isPlaylistActive ? 'is-playing' : ''}`}
                onClick={handlePlayAll}
                style={{ '--mood-color': meta.color }}
                aria-label={isPlaylistActive ? 'Currently playing' : 'Play all tracks'}
              >
                {isPlaylistActive ? (
                  <>
                    <div className="play-all-bars" aria-hidden="true">
                      <span /><span /><span />
                    </div>
                    Playing
                  </>
                ) : (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    Play All
                  </>
                )}
              </button>
              <span className="track-count-label">{tracks.length} tracks curated for you</span>
            </div>
          );
        })()}

        {/* Track List */}
        {tracks.length === 0 ? (
          <div className="no-tracks">
            <p>No tracks found for this mood yet. Try a different combination!</p>
            <button className="btn btn-outlined" onClick={onRestart}>Try Again</button>
          </div>
        ) : (
          <div className="tracks-grid">
            {tracks.map((track, idx) => {
              const isCurrentlyPlaying = player.hasQueue
                && player.currentIndex === idx
                && player.currentTrack?.id === track?.id;

              return (
                <div
                  className={`track-card ${isCurrentlyPlaying ? 'track-active' : ''}`}
                  key={track?.id ?? idx}
                  onClick={() => handlePlayTrack(idx)}
                  onMouseEnter={() => onInteraction?.()}
                >
                  <div className="track-position">
                    {isCurrentlyPlaying ? (
                      <div className="track-playing-bars" aria-label="Currently playing">
                        <span style={{ animationPlayState: player.isPlaying ? 'running' : 'paused' }} />
                        <span style={{ animationPlayState: player.isPlaying ? 'running' : 'paused' }} />
                        <span style={{ animationPlayState: player.isPlaying ? 'running' : 'paused' }} />
                      </div>
                    ) : (
                      String(idx + 1).padStart(2, '0')
                    )}
                  </div>
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
                  <button
                    className={`track-play-btn ${isCurrentlyPlaying ? 'track-play-active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePlayTrack(idx);
                    }}
                    title="Play this track"
                    aria-label={`Play ${track?.title ?? 'track'}`}
                  >
                    {isCurrentlyPlaying && player.isPlaying ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="6" y="4" width="4" height="16" rx="1"/>
                        <rect x="14" y="4" width="4" height="16" rx="1"/>
                      </svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                      </svg>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Bottom Actions */}
        <div className="results-actions">
          <button className="btn btn-outlined" onClick={onRestart}>
            Start Over
          </button>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage;
