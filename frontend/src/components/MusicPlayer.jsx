import React, { useState, useEffect, useRef } from 'react';
import { usePlayer } from './PlayerContext';
import { fetchYoutubeSearch } from '../api';
import './MusicPlayer.css';

const MusicPlayer = () => {
  const {
    currentTrack,
    currentIndex,
    queue,
    isPlaying,
    isMinimized,
    moodColor,
    moodLabel,
    embedKey,
    hasQueue,
    togglePlay,
    playNext,
    playPrevious,
    jumpTo,
    closePlayer,
    setIsMinimized,
  } = usePlayer();

  const [showQueue, setShowQueue] = useState(false);
  const [embedLoaded, setEmbedLoaded] = useState(false);
  const [youtubeVideoId, setYoutubeVideoId] = useState(null);
  const [isLoadingVideo, setIsLoadingVideo] = useState(false);

  const iframeRef = useRef(null);

  // Fetch YouTube video ID dynamically when track changes
  useEffect(() => {
    setEmbedLoaded(false);
    setYoutubeVideoId(null);

    if (!currentTrack) return;

    const artistName = currentTrack.artistId?.name || currentTrack.artistName || 'Unknown Artist';
    const query = `${currentTrack.title || ''} ${artistName !== 'Unknown Artist' ? artistName : ''} audio`;

    setIsLoadingVideo(true);
    fetchYoutubeSearch(query)
      .then(videoId => {
        if (videoId) setYoutubeVideoId(videoId);
      })
      .catch(err => console.error("Error fetching youtube id:", err))
      .finally(() => setIsLoadingVideo(false));

  }, [currentTrack, embedKey]);

  if (!hasQueue) return null;

  const artistName = currentTrack?.artistId?.name || currentTrack?.artistName || 'Unknown Artist';
  
  // Notice we use the exact video ID instead of listType=search
  const youtubeEmbedUrl = youtubeVideoId
    ? `https://www.youtube.com/embed/${youtubeVideoId}?autoplay=1`
    : null;

  if (isMinimized) {
    return (
      <div className="music-player-mini" style={{ '--player-accent': moodColor }}>
        <div className="mini-progress">
          <div className="mini-progress-fill" style={{ width: '100%' }} />
        </div>
        <div className="mini-content" onClick={() => setIsMinimized(false)}>
          <div className="mini-track-info">
            <div className="mini-now-playing-dot" style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
            <span className="mini-title">{currentTrack?.title || 'Unknown'}</span>
            <span className="mini-artist">{artistName}</span>
          </div>
          <div className="mini-controls">
            <button className="mini-btn" onClick={(e) => { e.stopPropagation(); playNext(); }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2"/></svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="music-player" style={{ '--player-accent': moodColor }}>
      {/* Top accent line */}
      <div className="player-accent-line" />

      {/* Header row */}
      <div className="player-header">
        <div className="player-mood-badge">
          <div className="now-playing-bars">
            <span style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
            <span style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
            <span style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
          </div>
          <span className="player-mood-text">{moodLabel || 'NOW PLAYING'}</span>
        </div>
        <div className="player-header-actions">
          <button
            className={`player-queue-btn ${showQueue ? 'active' : ''}`}
            onClick={() => setShowQueue(!showQueue)}
            title="Queue"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
              <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
            </svg>
            <span className="queue-count">{queue.length}</span>
          </button>
          <button className="player-minimize-btn" onClick={() => setIsMinimized(true)} title="Minimize">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
          <button className="player-close-btn" onClick={closePlayer} title="Close player">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>

      {/* Main player content */}
      <div className="player-body">
        {/* Track info */}
        <div className="player-track-info">
          <div className="player-album-art">
            <div className="album-art-fallback">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
              </svg>
            </div>
          </div>
          <div className="player-text">
            <h3 className="player-title">{currentTrack?.title || 'Unknown Track'}</h3>
            <p className="player-artist">{artistName}</p>
            {currentTrack?.language && (
              <span className="player-lang-badge">{currentTrack.language}</span>
            )}
          </div>
          <div className="player-track-counter">
            {currentIndex + 1} / {queue.length}
          </div>
        </div>

        {/* YouTube Player */}
        <div className="youtube-embed-container" style={{ margin: '0.5rem 0', borderRadius: '12px', overflow: 'hidden', height: '110px', background: '#111', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {isLoadingVideo && <span style={{ color: '#aaa', fontSize: '0.9rem' }}>Finding audio stream...</span>}
          {!isLoadingVideo && !youtubeEmbedUrl && <span style={{ color: '#ef4444', fontSize: '0.9rem' }}>Stream missing</span>}
          {youtubeEmbedUrl && (
            <iframe
              key={`yt-${youtubeVideoId}-${embedKey}`}
              ref={iframeRef}
              src={youtubeEmbedUrl}
              width="100%"
              height="100%"
              frameBorder="0"
              allow="autoplay; clipboard-write; encrypted-media; fullscreen"
              allowFullScreen
              loading="eager"
              title={`Play ${currentTrack?.title} on YouTube`}
              onLoad={() => setEmbedLoaded(true)}
              className={`youtube-embed ${embedLoaded ? 'loaded' : ''}`}
            />
          )}
        </div>

        {/* Controls — always visible */}
        <div className="player-controls">
          <button
            className="control-btn"
            onClick={playPrevious}
            disabled={currentIndex === 0}
            title="Previous"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2"/></svg>
          </button>

          <button
            className="control-btn"
            onClick={playNext}
            disabled={currentIndex >= queue.length - 1}
            title="Next"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2"/></svg>
          </button>
        </div>
      </div>

      {/* Queue panel */}
      {showQueue && (
        <div className="player-queue">
          <div className="queue-header">
            <span>UP NEXT</span>
            <span className="queue-total">{queue.length} tracks</span>
          </div>
          <div className="queue-list">
            {queue.map((track, idx) => (
              <div
                key={track.id || idx}
                className={`queue-item ${idx === currentIndex ? 'active' : ''} ${idx < currentIndex ? 'played' : ''}`}
                onClick={() => jumpTo(idx)}
              >
                <span className="queue-position">{String(idx + 1).padStart(2, '0')}</span>
                {idx === currentIndex && (
                  <div className="queue-playing-indicator">
                    <span style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
                    <span style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
                    <span style={{ animationPlayState: isPlaying ? 'running' : 'paused' }} />
                  </div>
                )}
                <div className="queue-track-info">
                  <span className="queue-title">{track.title || 'Unknown'}</span>
                  <span className="queue-artist">{track.artistId?.name || 'Unknown'}</span>
                </div>
                {track.durationMinutes && (
                  <span className="queue-duration">{track.durationMinutes}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MusicPlayer;
