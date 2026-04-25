import React, { createContext, useContext, useState, useCallback } from 'react';

const PlayerContext = createContext(null);

export const usePlayer = () => {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
};

export const PlayerProvider = ({ children }) => {
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [moodColor, setMoodColor] = useState('#818CF8');
  const [moodLabel, setMoodLabel] = useState('');
  // Incremented on every track change to force iframe reload
  const [embedKey, setEmbedKey] = useState(0);

  const currentTrack = currentIndex >= 0 && currentIndex < queue.length
    ? queue[currentIndex]
    : null;

  // Load and play a playlist
  const loadPlaylist = useCallback((tracks, startIdx = 0, mood = '', color = '#818CF8') => {
    setQueue(tracks);
    setCurrentIndex(startIdx);
    setIsPlaying(true);
    setIsMinimized(false);
    setMoodColor(color);
    setMoodLabel(mood);
    setEmbedKey(k => k + 1);
  }, []);

  // Play / Pause (No-op mostly used for UI state now since YouTube iframe manages itself)
  const togglePlay = useCallback(() => {
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  // Next track
  const playNext = useCallback(() => {
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setIsPlaying(true);
      setEmbedKey(k => k + 1);
    } else {
      setIsPlaying(false);
    }
  }, [currentIndex, queue.length]);

  // Previous track
  const playPrevious = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setIsPlaying(true);
      setEmbedKey(k => k + 1);
    }
  }, [currentIndex]);

  // Jump to specific track
  const jumpTo = useCallback((index) => {
    if (index >= 0 && index < queue.length) {
      setCurrentIndex(index);
      setIsPlaying(true);
      setEmbedKey(k => k + 1);
    }
  }, [queue.length]);

  // Close player
  const closePlayer = useCallback(() => {
    setQueue([]);
    setCurrentIndex(-1);
    setIsPlaying(false);
  }, []);

  const hasQueue = queue.length > 0;

  return (
    <PlayerContext.Provider
      value={{
        queue,
        currentTrack,
        currentIndex,
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
        loadPlaylist,
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
};
