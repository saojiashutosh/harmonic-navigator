import React, { useState, useEffect, useRef } from 'react';
import { usePlayer } from './PlayerContext';
import { fetchYoutubeSearch } from '../api';

const MusicPlayer = () => {
  const {
    currentTrack,
    embedKey,
    hasQueue,
    isPlaying,
    playNext,
    setProgress,
    setDuration,
    setSeekTo
  } = usePlayer();

  const [youtubeVideoId, setYoutubeVideoId] = useState(null);
  const playerRef = useRef(null);
  const iframeRef = useRef(null);

  // Load Youtube Iframe API
  useEffect(() => {
    if (!window.YT) {
      const tag = document.createElement('script');
      tag.src = "https://www.youtube.com/iframe_api";
      const firstScriptTag = document.getElementsByTagName('script')[0];
      firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
    }
  }, []);

  useEffect(() => {
    setYoutubeVideoId(null);
    if (!currentTrack) return;

    const artistName = currentTrack.artistId?.name || currentTrack.artistName || '';
    const title = currentTrack.title || '';
    const parts = [title, artistName].filter(Boolean);
    const query = parts.length > 0 ? `${parts.join(' - ')} official audio` : '';

    if (!query) return;

    fetchYoutubeSearch(query)
      .then(videoId => {
        if (videoId) setYoutubeVideoId(videoId);
      })
      .catch(err => console.error("Error fetching youtube id:", err));

  }, [currentTrack, embedKey]);

  // Init Player
  useEffect(() => {
    if (!youtubeVideoId || !iframeRef.current) return;
    
    let isDestroyed = false;

    const initPlayer = () => {
      if (isDestroyed) return;
      if (playerRef.current) playerRef.current.destroy();

      playerRef.current = new window.YT.Player(iframeRef.current, {
        videoId: youtubeVideoId,
        playerVars: { autoplay: 1, controls: 0, playsinline: 1 },
        events: {
          onReady: (event) => {
            if (isDestroyed) return;
            setDuration(event.target.getDuration());
            
            // Set seek function in context
            setSeekTo(() => (ratio) => {
              if (playerRef.current && playerRef.current.getDuration) {
                const dur = playerRef.current.getDuration();
                if (dur) playerRef.current.seekTo(ratio * dur, true);
              }
            });

            if (isPlaying) event.target.playVideo();
            else event.target.pauseVideo();
          },
          onStateChange: (event) => {
            if (isDestroyed) return;
            if (event.data === window.YT.PlayerState.ENDED) {
              playNext();
            }
          }
        }
      });
    };

    if (window.YT && window.YT.Player) {
      initPlayer();
    } else {
      window.onYouTubeIframeAPIReady = initPlayer;
    }

    return () => {
      isDestroyed = true;
      if (playerRef.current) {
        try { playerRef.current.destroy(); } catch (e) {}
        playerRef.current = null;
      }
    };
  }, [youtubeVideoId]);

  // Sync Play/Pause
  useEffect(() => {
    if (playerRef.current && playerRef.current.playVideo) {
      if (isPlaying) playerRef.current.playVideo();
      else playerRef.current.pauseVideo();
    }
  }, [isPlaying]);

  // Track Progress
  useEffect(() => {
    const interval = setInterval(() => {
      if (playerRef.current && playerRef.current.getCurrentTime && isPlaying) {
        const dur = playerRef.current.getDuration();
        if (dur > 0) {
          setProgress(playerRef.current.getCurrentTime() / dur);
        }
      }
    }, 250);
    return () => clearInterval(interval);
  }, [isPlaying, setProgress]);

  if (!hasQueue || !youtubeVideoId) return null;

  return (
    <div style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      <div ref={iframeRef}></div>
    </div>
  );
};

export default MusicPlayer;
