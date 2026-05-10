import React, { useState, useEffect, useRef } from 'react';
import { usePlayer } from './PlayerContext';
import { fetchSaavnSearch } from '../api';

const SKIP_DELAY_MS = 3000;

const MusicPlayer = () => {
  const {
    currentTrack,
    embedKey,
    isPlaying,
    playNext,
    setProgress,
    setDuration,
    setSeekTo,
    setIsLoadingAudio,
    audioRef,
  } = usePlayer();

  const [audioUrl, setAudioUrl] = useState(null);
  const audioEl = useRef(null);
  const skipTimerRef = useRef(null);
  const isPlayingRef = useRef(isPlaying);
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);

  // Register this component's <audio> element with the shared context ref
  useEffect(() => {
    audioRef.current = audioEl.current;
    return () => { audioRef.current = null; };
  }, []); // runs once on mount / cleanup on unmount

  const clearSkipTimer = () => {
    if (skipTimerRef.current) { clearTimeout(skipTimerRef.current); skipTimerRef.current = null; }
  };

  // Resolve audio URL whenever the track changes
  useEffect(() => {
    setAudioUrl(null);
    clearSkipTimer();

    if (!currentTrack) {
      setIsLoadingAudio(false);
      return;
    }

    // Use cached URL from DB if available
    if (currentTrack.streamUrl) {
      setAudioUrl(currentTrack.streamUrl);
      return;
    }

    const title = (currentTrack.title || '').trim();
    const artist = (currentTrack.artistId?.name || currentTrack.artistName || '').trim();
    const query = title && artist ? `${title} ${artist}` : title || artist;
    if (!query) { setIsLoadingAudio(false); return; }

    let cancelled = false;
    setIsLoadingAudio(true);

    const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const dbId = UUID_RE.test(currentTrack.id) ? currentTrack.id : null;

    (async () => {
      let url = await fetchSaavnSearch(query, dbId).catch(() => null);
      if (!url && artist) url = await fetchSaavnSearch(title, dbId).catch(() => null);
      if (cancelled) return;
      setIsLoadingAudio(false);
      if (url) {
        setAudioUrl(url);
      } else {
        skipTimerRef.current = setTimeout(() => { if (!cancelled) playNext(); }, SKIP_DELAY_MS);
      }
    })();

    return () => { cancelled = true; clearSkipTimer(); };
  }, [currentTrack?.id, embedKey]);

  // Wire the audio element to the URL
  useEffect(() => {
    const audio = audioEl.current;
    if (!audio) return;

    if (!audioUrl) {
      audio.pause();
      audio.src = '';
      return;
    }

    audio.src = audioUrl;
    audio.load();

    const onMeta = () => {
      setDuration(audio.duration);
      setSeekTo(() => (ratio) => {
        if (audioEl.current && audioEl.current.duration) {
          audioEl.current.currentTime = ratio * audioEl.current.duration;
        }
      });
    };
    const onCanPlay = () => { if (isPlayingRef.current) audio.play().catch(() => {}); };
    const onTime = () => { if (audio.duration > 0) setProgress(audio.currentTime / audio.duration); };
    const onEnd = () => playNext();
    const onError = () => { skipTimerRef.current = setTimeout(playNext, SKIP_DELAY_MS); };

    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('canplay', onCanPlay);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('ended', onEnd);
    audio.addEventListener('error', onError);

    if (isPlayingRef.current) audio.play().catch(() => {});

    return () => {
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('canplay', onCanPlay);
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('ended', onEnd);
      audio.removeEventListener('error', onError);
    };
  }, [audioUrl]);

  // Sync play/pause state from context
  useEffect(() => {
    const audio = audioEl.current;
    if (!audio) return;
    if (isPlaying) {
      if (audioUrl) audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, [isPlaying, audioUrl]);

  // Always render so the element exists before the first play() unlock call
  return <audio ref={audioEl} style={{ display: 'none' }} preload="auto" />;
};

export default MusicPlayer;
