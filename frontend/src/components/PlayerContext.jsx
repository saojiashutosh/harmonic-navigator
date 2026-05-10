import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

const PlayerContext = createContext(null);

export const usePlayer = () => {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
};

function safePlay(audio) {
  if (!audio) return;
  try {
    const p = audio.play();
    if (p && typeof p.catch === 'function') p.catch(() => {});
  } catch (_) {}
}

export const PlayerProvider = ({ children }) => {
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [moodColor, setMoodColor] = useState('#5B8A8A');
  const [moodLabel, setMoodLabel] = useState('');
  const [embedKey, setEmbedKey] = useState(0);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [seekTo, setSeekTo] = useState(null);

  // Refs so callbacks are stable (no deps) and always read current values
  const audioRef = useRef(null);        // assigned by MusicPlayer on mount
  const currentIndexRef = useRef(-1);
  const queueLengthRef = useRef(0);
  const isPlayingRef = useRef(false);

  useEffect(() => { currentIndexRef.current = currentIndex; }, [currentIndex]);
  useEffect(() => { queueLengthRef.current = queue.length; }, [queue.length]);
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);

  const currentTrack = currentIndex >= 0 && currentIndex < queue.length
    ? queue[currentIndex]
    : null;

  const loadPlaylist = useCallback((tracks, startIdx = 0, mood = '', color = '#5B8A8A') => {
    setQueue(tracks);
    setCurrentIndex(startIdx);
    setIsPlaying(true);
    setIsMinimized(false);
    setMoodColor(color);
    setMoodLabel(mood);
    setEmbedKey(k => k + 1);
    setProgress(0);
    safePlay(audioRef.current); // unlock autoplay within the user gesture
  }, []);

  const togglePlay = useCallback(() => {
    const next = !isPlayingRef.current;
    if (next) safePlay(audioRef.current); // unlock before state update
    setIsPlaying(next);
  }, []);

  const playNext = useCallback(() => {
    const ci = currentIndexRef.current;
    const ql = queueLengthRef.current;
    if (ci < ql - 1) {
      setCurrentIndex(ci + 1);
      setIsPlaying(true);
      setEmbedKey(k => k + 1);
      setProgress(0);
      safePlay(audioRef.current);
    } else {
      setIsPlaying(false);
    }
  }, []);

  const playPrevious = useCallback(() => {
    const ci = currentIndexRef.current;
    if (ci > 0) {
      setCurrentIndex(ci - 1);
      setIsPlaying(true);
      setEmbedKey(k => k + 1);
      setProgress(0);
      safePlay(audioRef.current);
    }
  }, []);

  const jumpTo = useCallback((index) => {
    const ql = queueLengthRef.current;
    if (index >= 0 && index < ql) {
      setCurrentIndex(index);
      setIsPlaying(true);
      setEmbedKey(k => k + 1);
      setProgress(0);
      safePlay(audioRef.current);
    }
  }, []);

  const closePlayer = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }
    setQueue([]);
    setCurrentIndex(-1);
    setIsPlaying(false);
    setProgress(0);
    setDuration(0);
    setIsLoadingAudio(false);
  }, []);

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
        hasQueue: queue.length > 0,
        isLoadingAudio,
        setIsLoadingAudio,
        audioRef,
        togglePlay,
        playNext,
        playPrevious,
        jumpTo,
        closePlayer,
        setIsMinimized,
        loadPlaylist,
        progress,
        setProgress,
        duration,
        setDuration,
        seekTo,
        setSeekTo,
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
};
