import React, { useState } from 'react';
import * as API from '../api';
import { usePlayer } from './PlayerContext';
import './ConcertMode.css';

const CONCERT_COLOR = '#C26F3C';

// Cities AllEvents covers well — used for the type-ahead suggestions.
const INDIAN_CITIES = [
  'Mumbai', 'Delhi', 'Bengaluru', 'Hyderabad', 'Chennai', 'Kolkata',
  'Pune', 'Ahmedabad', 'Jaipur', 'Chandigarh', 'Gurugram', 'Noida',
  'Kochi', 'Goa', 'Indore', 'Lucknow', 'Nagpur', 'Coimbatore',
  'Surat', 'Bhopal', 'Visakhapatnam', 'Guwahati',
];

const formatDate = (iso) => {
  if (!iso) return 'date to be announced';
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch {
    return iso;
  }
};

const trackArtist = (t) => t.artistName || t.artistId?.name || 'unknown';

/* ── A single discovered concert ───────────────────────────── */
function ConcertCard({ event, onGetReady, generating }) {
  return (
    <article className="cm-card">
      <div className="cm-card-head">
        <span className="cm-card-artist">{event.artistName || event.name}</span>
        {event.eventDate && <time className="cm-card-date">{formatDate(event.eventDate)}</time>}
      </div>
      <p className="cm-card-event">{event.name}</p>
      <p className="cm-card-venue">
        {[event.venueName, event.city, event.country].filter(Boolean).join(' · ') || '—'}
      </p>
      <div className="cm-card-actions">
        <button
          className="og-btn og-btn-primary og-btn-sm"
          onClick={() => onGetReady(event)}
          disabled={generating}
        >
          {generating ? 'tuning up…' : `get ready ▸`}
        </button>
        {event.ticketUrl && (
          <a
            className="og-btn og-btn-ghost og-btn-sm"
            href={event.ticketUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            tickets ↗
          </a>
        )}
      </div>
    </article>
  );
}

/* ── The generated concert-prep playlist ───────────────────── */
function ConcertPlaylistPanel({ event, tracks, onPlay }) {
  const setlistCount = Array.isArray(event?.recentSetlist) ? event.recentSetlist.length : 0;

  return (
    <section className="cm-playlist">
      <header className="cm-playlist-head">
        <span className="og-eyebrow">your warm-up set</span>
        <h2>get ready for {event?.artistName || 'the show'}.</h2>
        <p>
          {tracks.length} tracks
          {setlistCount > 0
            ? ` · weighted toward ${setlistCount} songs from recent setlists`
            : ' · drawn from this artist’s catalogue'}
          .
        </p>
        <button className="og-btn og-btn-primary" onClick={() => onPlay(0)}>
          play the warm-up ▸
        </button>
      </header>
      <ol className="cm-tracklist">
        {tracks.map((t, i) => (
          <li key={t.id || i}>
            <button className="cm-track" onClick={() => onPlay(i)}>
              <span className="cm-track-n">{String(i + 1).padStart(2, '0')}</span>
              <span className="cm-track-info">
                <span className="cm-track-title">{t.title}</span>
                <span className="cm-track-artist">{trackArtist(t)}</span>
              </span>
              {t.selectionReason === 'tag_match' && (
                <span className="cm-track-tag" title="from a recent setlist">setlist</span>
              )}
              <span className="cm-track-dur">{t.durationMinutes || ''}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ── Concert Mode view ─────────────────────────────────────── */
export default function ConcertMode({ onBack }) {
  const { loadPlaylist } = usePlayer();
  const [city, setCity] = useState('');
  const [searchedCity, setSearchedCity] = useState('');
  const [events, setEvents] = useState(null); // null → not searched yet
  const [searching, setSearching] = useState(false);
  const [generatingId, setGeneratingId] = useState(null);
  const [active, setActive] = useState(null); // { event, tracks }
  const [error, setError] = useState(null);
  const [apiNote, setApiNote] = useState(null);
  const [showSuggest, setShowSuggest] = useState(false);

  // Suggestions: filter the city list by what's typed (substring, case-
  // insensitive); show a starter set when the field is empty.
  const query = city.trim().toLowerCase();
  const suggestions = (
    query
      ? INDIAN_CITIES.filter((c) => c.toLowerCase().includes(query) && c.toLowerCase() !== query)
      : INDIAN_CITIES
  ).slice(0, 6);

  const search = async (e, cityArg) => {
    e?.preventDefault?.();
    const trimmed = (cityArg ?? city).trim();
    if (!trimmed || searching) return;
    setShowSuggest(false);
    setSearching(true);
    setError(null);
    setApiNote(null);
    setActive(null);
    try {
      const data = await API.discoverConcerts(trimmed);
      setEvents(data.events || []);
      setSearchedCity(data.city || trimmed);
      setApiNote(data.apiError || null);
    } catch (err) {
      setError(err.message);
      setEvents(null);
    } finally {
      setSearching(false);
    }
  };

  const pickCity = (name) => {
    setCity(name);
    setShowSuggest(false);
    search(null, name);
  };

  const getReady = async (event) => {
    if (generatingId) return;
    setGeneratingId(event.id);
    setError(null);
    try {
      const cp = await API.generateConcertPlaylist(event.id);
      const playlistId = cp.playlist?.id || cp.playlistId;
      const rows = await API.fetchPlaylistTracks(playlistId);
      const tracks = rows.map((r) => ({ ...r.track, relevanceScore: r.relevanceScore }));
      if (!tracks.length) {
        setError('No playable tracks for this artist yet — try another concert.');
        return;
      }
      setActive({ event: cp.concertEvent || event, tracks });
      loadPlaylist(tracks, 0, 'concert', CONCERT_COLOR);
    } catch (err) {
      setError(err.message);
    } finally {
      setGeneratingId(null);
    }
  };

  const playActive = (i) => {
    if (active) loadPlaylist(active.tracks, i, 'concert', CONCERT_COLOR);
  };

  return (
    <div className="cm">
      <div className="cm-intro">
        <button className="og-btn og-btn-ghost og-btn-sm cm-back" onClick={onBack}>
          ← back
        </button>
        <span className="og-eyebrow">concert mode</span>
        <h1>
          there&rsquo;s a show<br /><em>near you</em>.
        </h1>
        <p>
          Tell us your city. We&rsquo;ll find upcoming concerts for artists you can
          hear here — and tie a warm-up playlist around what they&rsquo;ve been
          playing live.
        </p>

        <form className="cm-search" onSubmit={search} autoComplete="off">
          <div className="cm-search-field">
            <input
              className="cm-search-input"
              type="text"
              placeholder="your city — Mumbai, Delhi, Bengaluru…"
              value={city}
              maxLength={128}
              onChange={(e) => { setCity(e.target.value); setShowSuggest(true); }}
              onFocus={() => setShowSuggest(true)}
              onBlur={() => setTimeout(() => setShowSuggest(false), 120)}
            />
            {showSuggest && suggestions.length > 0 && (
              <ul className="cm-suggest">
                {suggestions.map((name) => (
                  <li key={name}>
                    <button
                      type="button"
                      className="cm-suggest-item"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pickCity(name)}
                    >
                      <span className="cm-suggest-pin" aria-hidden="true">◍</span>
                      {name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button
            type="submit"
            className="og-btn og-btn-primary"
            disabled={searching || !city.trim()}
          >
            {searching ? 'looking…' : 'find concerts'}
          </button>
        </form>

        {error && <p className="cm-error">{error}</p>}
      </div>

      {events !== null && (
        <div className="cm-results">
          {apiNote && (
            <p className="cm-note">
              Live discovery hiccuped — showing concerts already on file.
            </p>
          )}
          {events.length === 0 ? (
            <p className="cm-empty">
              No concerts found in {searchedCity} for artists in our catalogue yet.
              Try a bigger city, or check back later.
            </p>
          ) : (
            <>
              <span className="cm-results-count">
                {events.length} concert{events.length === 1 ? '' : 's'} in {searchedCity}
              </span>
              <div className="cm-grid">
                {events.map((event) => (
                  <ConcertCard
                    key={event.id}
                    event={event}
                    onGetReady={getReady}
                    generating={generatingId === event.id}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {active && (
        <ConcertPlaylistPanel
          event={active.event}
          tracks={active.tracks}
          onPlay={playActive}
        />
      )}
    </div>
  );
}
