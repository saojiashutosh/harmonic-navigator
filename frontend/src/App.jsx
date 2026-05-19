import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import './index.css';
import { PlayerProvider, usePlayer } from './components/PlayerContext';
import MusicPlayer from './components/MusicPlayer';
import ConcertMode from './components/ConcertMode';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthModal from './components/AuthModal';
import * as API from './api';
import HS from './utils/HarmonicShared';

/**
 * Ask the browser for the laptop's LAN-routable address via a WebRTC ICE
 * candidate. No actual peer connection is opened. Prefers a real IPv4
 * (e.g. 192.168.1.42) so a phone on the same Wi-Fi can hit it directly.
 * Falls back to the mDNS hostname (xxxx.local) modern browsers return for
 * privacy — that name also resolves on most phones on the same network.
 */
async function detectLanHost() {
  if (typeof RTCPeerConnection === 'undefined') return null;
  return new Promise((resolve) => {
    let pc;
    try { pc = new RTCPeerConnection({ iceServers: [] }); }
    catch { return resolve(null); }
    const ipv4s = [];
    const mdns = [];
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      try { pc.close(); } catch {}
      resolve(ipv4s[0] || mdns[0] || null);
    };
    pc.onicecandidate = (e) => {
      if (!e.candidate) return finish();
      // Candidate line: "candidate:... <addr> <port> typ host ..."
      const parts = e.candidate.candidate.split(' ');
      const addr = parts[4];
      if (!addr) return;
      if (/^\d+\.\d+\.\d+\.\d+$/.test(addr) && !addr.startsWith('127.')) ipv4s.push(addr);
      else if (addr.endsWith('.local')) mdns.push(addr);
    };
    try { pc.createDataChannel(''); } catch {}
    pc.createOffer().then(o => pc.setLocalDescription(o)).catch(finish);
    setTimeout(finish, 1500);
  });
}

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

/* ── Orbital loader ──────────────────────────────────────── */
function OrbitalLoader({ label = 'setting the field…' }) {
  const cx = 140, cy = 140;
  const rings = [22, 42, 64, 88, 114];
  return (
    <div className="og-orbital-overlay">
      <svg width="280" height="280" viewBox="0 0 280 280" fill="none" aria-hidden="true">
        {/* Static dashed rings */}
        {rings.map((r, i) => (
          <circle key={r} cx={cx} cy={cy} r={r}
            stroke="var(--sage)" strokeWidth={i === 0 ? 0.8 : 0.6}
            strokeDasharray={i % 2 === 0 ? '2 4' : '1 5'}
            opacity={0.35 + i * 0.04} fill="none" />
        ))}

        {/* Orbiting dot — ring 1 (fastest) */}
        <g className="og-orbit-r1">
          <circle cx={cx + rings[0]} cy={cy} r="3.5" fill="var(--accent)" opacity="0.9" />
        </g>

        {/* Orbiting dot — ring 2 */}
        <g className="og-orbit-r2">
          <circle cx={cx + rings[1]} cy={cy} r="4.5" fill="var(--accent)" opacity="0.75" />
          <circle cx={cx - rings[1]} cy={cy} r="2.5" fill="var(--sage)" opacity="0.5" />
        </g>

        {/* Orbiting dots — ring 3 */}
        <g className="og-orbit-r3">
          <circle cx={cx + rings[2]} cy={cy} r="5" fill="var(--accent)" opacity="0.7" />
          <circle cx={cx} cy={cy + rings[2]} r="3" fill="var(--sage)" opacity="0.4" />
        </g>

        {/* Orbiting dot — ring 4 */}
        <g className="og-orbit-r4">
          <circle cx={cx + rings[3]} cy={cy} r="4" fill="var(--accent)" opacity="0.55" />
          <circle cx={cx - rings[3]} cy={cy} r="2.5" fill="var(--ink-faint)" opacity="0.4" />
          <circle cx={cx} cy={cy - rings[3]} r="3" fill="var(--sage)" opacity="0.35" />
        </g>

        {/* Outer asteroid belt */}
        <g className="og-orbit-belt">
          {Array.from({ length: 6 }).map((_, i) => {
            const a = (i / 6) * Math.PI * 2;
            return <circle key={i}
              cx={cx + Math.cos(a) * rings[4]}
              cy={cy + Math.sin(a) * rings[4]}
              r={i % 2 === 0 ? 3 : 2}
              fill="var(--accent)" opacity={i % 2 === 0 ? 0.6 : 0.35} />;
          })}
        </g>

        {/* Centre sun */}
        <circle cx={cx} cy={cy} r="9" fill="var(--accent)" opacity="0.95" />
        <circle cx={cx} cy={cy} r="5" fill="var(--paper)" opacity="0.6" />
      </svg>
      <span className="og-orbital-label">{label}</span>
    </div>
  );
}

/* ── Ambient music-reactive background ──────────────────── */
function AmbientLayer() {
  const { isPlaying, moodLabel, currentTrack } = usePlayer();
  const mood = (moodLabel || '').toLowerCase();
  const live = !!currentTrack && isPlaying;
  const present = !!currentTrack;

  return (
    <div className={`og-ambient${present ? (live ? ' is-live' : ' is-idle') : ''}`} aria-hidden="true">
      {/* Soft gradient orbs — always float when a track is loaded */}
      <span className="ogab ogab-1" />
      <span className="ogab ogab-2" />
      <span className="ogab ogab-3" />

      {/* Celebratory: orbiting rings + travelling dots */}
      {mood === 'celebratory' && <>
        <span className="ogab-ring ogab-ring-1" />
        <span className="ogab-ring ogab-ring-2" />
        <span className="ogab-ring ogab-ring-3" />
        {[180, 280, 380].map((r, i) => (
          <span key={r}
            className={`ogab-orb-arm${i % 2 ? ' ogab-rev' : ''}`}
            style={{ '--r': `${r}px`, '--spd': `${22 + i * 12}s` }}>
            <span className="ogab-dot" style={{ '--dot-r': i % 2 === 0 ? '6px' : '4px' }} />
          </span>
        ))}
      </>}

      {/* Energized: expanding pulse rings */}
      {mood === 'energized' && <>
        {[0, 1, 2, 3].map(i => (
          <span key={i} className="ogab-pulse" style={{ '--d': `${i * 0.9}s` }} />
        ))}
      </>}

      {/* Calm: very slow large breathing blob */}
      {mood === 'calm' && <span className="ogab-calm-blob" />}

      {/* Melancholic: slow diagonal rain streaks */}
      {mood === 'melancholic' && Array.from({ length: 8 }).map((_, i) => (
        <span key={i} className="ogab-streak" style={{ '--x': `${10 + i * 12}%`, '--d': `${i * 0.7}s` }} />
      ))}

      {/* Focused: breathing concentric rings */}
      {mood === 'focused' && <>
        <span className="ogab-focus-ring ogab-focus-1" />
        <span className="ogab-focus-ring ogab-focus-2" />
      </>}
    </div>
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
function Header({ onHome, onMyPlaylists, onConcertMode, onLogout, view }) {
  const { user, openAuth } = useAuth();

  return (
    <header className="og-header">
      <button className="og-logo" onClick={onHome}>
        <HarmonicMark size={34} />
        <span>Harmonic Navigator</span>
      </button>
      <div className="og-header-auth">
        <button
          className={`og-btn og-btn-ghost og-btn-sm ${view === 'concert' ? 'is-active' : ''}`}
          onClick={onConcertMode}
        >
          concert mode
        </button>
        {user ? (
          <>
            <button
              className={`og-btn og-btn-ghost og-btn-sm ${view === 'mylists' ? 'is-active' : ''}`}
              onClick={onMyPlaylists}
            >
              my playlists
            </button>
            <span className="og-auth-name">{user.firstName}</span>
            <button className="og-btn og-btn-ghost og-btn-sm" onClick={onLogout}>sign out</button>
          </>
        ) : (
          <button className="og-btn og-btn-ghost og-btn-sm" onClick={() => openAuth('signin')}>sign in</button>
        )}
      </div>
    </header>
  );
}

/* ── Save-as modal ─────────────────────────────────────── */
function SavePlaylistModal({ open, defaultName, onClose, onSave }) {
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (open) { setName(defaultName || ''); setErr(null); }
  }, [open, defaultName]);

  if (!open) return null;

  const submit = async (e) => {
    e?.preventDefault?.();
    const trimmed = name.trim();
    if (!trimmed) { setErr('please give it a name'); return; }
    setSaving(true); setErr(null);
    try {
      await onSave(trimmed);
      onClose();
    } catch (e) { setErr(e.message || 'could not save'); setSaving(false); }
  };

  return (
    <div className="og-modal-backdrop" onClick={onClose}>
      <form className="og-modal" onClick={e => e.stopPropagation()} onSubmit={submit}>
        <h3>name your playlist</h3>
        <p className="og-modal-sub">a small label, for when you come back to it.</p>
        <input
          autoFocus
          className="og-modal-input"
          placeholder="rainy tuesday, focus hour…"
          value={name}
          maxLength={120}
          onChange={e => setName(e.target.value)}
        />
        {err && <span className="og-modal-err">{err}</span>}
        <div className="og-modal-actions">
          <button type="button" className="og-btn og-btn-ghost" onClick={onClose} disabled={saving}>cancel</button>
          <button type="submit" className="og-btn og-btn-primary" disabled={saving}>
            {saving ? 'saving…' : 'save playlist'}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ── Add-to-playlist popover ───────────────────────────── */
function AddToPlaylistPopover({ open, onClose, onPick, loading, playlists, error }) {
  if (!open) return null;
  return (
    <div className="og-pop-backdrop" onClick={onClose}>
      <div className="og-pop" onClick={e => e.stopPropagation()}>
        <header>add to playlist</header>
        {loading ? (
          <p className="og-pop-empty">loading…</p>
        ) : error ? (
          <p className="og-pop-empty">{error}</p>
        ) : playlists.length === 0 ? (
          <p className="og-pop-empty">no saved playlists yet. create one first.</p>
        ) : (
          <ul className="og-pop-list">
            {playlists.map(sp => (
              <li key={sp.id}>
                <button onClick={() => onPick(sp)}>
                  <span className="og-pop-name">{sp.name || 'untitled'}</span>
                  <span className="og-pop-meta">{sp.playlist?.moodLabel || '—'} · {sp.playlist?.trackCount || 0}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <footer><button className="og-btn og-btn-ghost og-btn-sm" onClick={onClose}>close</button></footer>
      </div>
    </div>
  );
}

/* ── Hero preview card ───────────────────────────────────── */
const PREVIEW_TRACKS = [
  { id: 'prev-1', title: 'Kesariya', artistId: { name: 'Arijit Singh' }, durationMinutes: '4:28', language: 'hindi' },
  { id: 'prev-2', title: 'Tum Hi Ho', artistId: { name: 'Arijit Singh' }, durationMinutes: '4:22', language: 'hindi' },
  { id: 'prev-3', title: 'Tujh Mein Rab Dikhta Hai', artistId: { name: 'Roop Kumar Rathod' }, durationMinutes: '4:43', language: 'hindi' },
  { id: 'prev-4', title: 'Apna Bana Le', artistId: { name: 'Arijit Singh' }, durationMinutes: '4:10', language: 'hindi' },
  { id: 'prev-5', title: 'Kal Ho Naa Ho', artistId: { name: 'Sonu Nigam' }, durationMinutes: '5:22', language: 'hindi' },
];

function HeroPreviewCard() {
  const { loadPlaylist, jumpTo, queue, currentTrack, isPlaying } = usePlayer();

  const handlePlay = (idx = 0) => {
    if (queue.length > 0 && queue[0].id === PREVIEW_TRACKS[0].id) {
      jumpTo(idx);
    } else {
      loadPlaylist(PREVIEW_TRACKS, idx, 'celebratory', '#C26F3C');
    }
  };

  return (
    <div className="og-hero-right">
      <div className="og-preview-card">
        <div className="og-pc-header">
          <div className="og-pc-sigil">
            <MoodSigil mood="celebratory" drawIn={false} size={64} />
          </div>
          <div className="og-pc-meta">
            <div className="og-pc-mood">celebratory.</div>
            <div className="og-pc-badge">your reading · sample</div>
          </div>
          <div className="og-pc-conf">93%</div>
        </div>
        <div className="og-pc-tracks">
          {PREVIEW_TRACKS.map((t, i) => {
            const active = currentTrack?.id === t.id;
            return (
              <button key={t.id} className={`og-pc-track${active ? ' is-active' : ''}`} onClick={() => handlePlay(i)}>
                <span className="og-pc-tn">{String(i + 1).padStart(2, '0')}</span>
                <div className="og-pc-track-info">
                  <span className="og-pc-tt">{t.title}{active && <em> · {isPlaying ? '▶' : '❚❚'}</em>}</span>
                  <span className="og-pc-ta">{t.artistId.name}</span>
                </div>
                <span className="og-pc-td">{t.durationMinutes}</span>
              </button>
            );
          })}
        </div>
        <div className="og-pc-footer">
          <div className="og-pc-stats">
            <dl className="og-pc-stat"><dt>match</dt><dd>93%</dd></dl>
            <dl className="og-pc-stat"><dt>tracks</dt><dd>15</dd></dl>
            <dl className="og-pc-stat"><dt>length</dt><dd>~60m</dd></dl>
          </div>
          <button className="og-pc-play" onClick={() => handlePlay(0)}>▶</button>
        </div>
      </div>
      <div className="og-pc-float-1" aria-hidden="true"><Botanical mood="calm" size={72} /></div>
      <div className="og-pc-float-2" aria-hidden="true"><Botanical mood="focused" size={56} /></div>
    </div>
  );
}

/* ── Landing ─────────────────────────────────────────────── */
function Landing({ onStart, onStartGroup, onJoinGroup, onConcertMode }) {
  return (
    <div className="og-landing">
      <div className="og-hero">
        <div className="og-hero-left">
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
            <span className="og-hero-aside">~ 3 min · no account · 15 tracks</span>
          </div>
          <div className="og-hero-group">
            <button className="og-btn og-btn-ghost" onClick={onStartGroup}>listen together ◌</button>
            <button className="og-btn og-btn-ghost og-btn-sm" onClick={onJoinGroup}>have a code?</button>
            <button className="og-btn og-btn-ghost og-btn-sm" onClick={onConcertMode}>concert mode ♪</button>
          </div>
        </div>
        <HeroPreviewCard />
      </div>

      <div className="og-three">
        {[
          { n: 'one', t: 'A small conversation', d: 'A few gentle questions, on a single page. Your words, your weather.', e: 0.3, m: 'calm' },
          { n: 'two', t: 'A reading of the room', d: 'We listen for the shape — energy, intent, the colour of the hour.', e: 0.55, m: 'focused' },
          { n: 'three', t: 'A hand-tied bouquet', d: 'Ten to fifteen tracks. Picked, not generated. Press play, or browse.', e: 0.85, m: 'celebratory' },
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

function MoodCard({ onComplete, onGuestLimit, groupContext }) {
  const { closePlayer } = usePlayer();
  const { openAuth } = useAuth();
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
        // Force music_language to single-select even if the API still says multi_select
        // (until sync_mood_questions has been run against the DB).
        const normalized = qs.map(q => q.key === 'music_language' ? { ...q, inputType: 'select' } : q);
        setQuestions(normalized); setSessionId(sess.id); setLoading(false);
      } catch (err) {
        if (cancelled) return;
        if (err.status === 403 && err.code === 'GUEST_LIMIT_REACHED') {
          openAuth('signup', 'You\'ve used your 2 free sessions. Sign up to keep listening — 60 tracks, unlimited sessions.');
          if (onGuestLimit) onGuestLimit();
          return;
        }
        setError('Could not load.');
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const select = (q, v) => {
    if (q.inputType === 'multi_select') {
      setAnswers(p => {
        const cur = Array.isArray(p[q.key]) ? p[q.key] : [];
        const next = cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v];
        return { ...p, [q.key]: next };
      });
    } else {
      setAnswers(p => ({ ...p, [q.key]: v }));
    }
    setBleedKey(`${q.key}-${v}-${Date.now()}`);
  };
  // Slider counts every question; submit is still gated only by single-selects
  // (multi_select + text remain optional — leaving them blank doesn't block).
  const selectRequired = questions.filter(q => q.inputType === 'select');
  const selectAnswered = selectRequired.filter(q => answers[q.key] !== undefined).length;
  const hasAnswer = (q) => {
    const v = answers[q.key];
    if (q.inputType === 'multi_select') return Array.isArray(v) && v.length > 0;
    if (q.inputType === 'text') return q.key in answers;  // typed OR skipped both count
    return v !== undefined;
  };
  const total = questions.length || 1;
  const answered = questions.filter(hasAnswer).length;
  const ready = selectRequired.length > 0 && selectAnswered >= selectRequired.length;
  const remaining = selectRequired.length - selectAnswered;

  const submit = async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    closePlayer();
    try {
      const inf = await API.submitAnswers(sessionId, answers);
      if (groupContext?.groupId) {
        // Group flow: link this survey to the lobby; the host generates
        // the blended playlist when everyone's ready.
        await API.attachMoodSessionToGroup(
          groupContext.groupId,
          groupContext.participantId,
          inf.moodSessionId,
        );
        onComplete({ groupReturn: true });
        return;
      }
      const pl = await API.generatePlaylist(inf.moodSessionId, 15);
      const tracks = await API.fetchPlaylistTracks(pl.id);
      onComplete({
        moodLabel: inf.moodLabel,
        confidence: inf.confidence,
        tracks: tracks.map(t => ({ ...t.track, relevanceScore: t.relevanceScore })),
        playlistId: pl.id,
      });
    } catch (err) { setError('Failed: ' + err.message); setSubmitting(false); submittedRef.current = false; }
  };

  if (loading) return <OrbitalLoader label="setting the field…" />;
  if (submitting) return <OrbitalLoader label="tying the bouquet…" />;
  if (error) return <div className="og-loading"><p>{error}</p></div>;

  return (
    <div className="og-mood">
      <aside className="og-mood-rail">
        <div className="og-rail-sticky">
          <span className="og-eyebrow">a session · {new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase()}</span>
          <h1>tell me how the<br /><em>day feels</em>.</h1>
          <p>a few quiet questions, on one page. nothing is fixed; you can change your mind as you go.</p>
          <div className="og-rail-progress">
            <div className="og-rail-track">
              {Array.from({ length: total }).map((_, i) => (
                <span key={i} className={`og-rail-dot ${i < answered ? 'is-filled' : ''}`} />
              ))}
            </div>
            <span className="og-rail-count">{answered} of {total}</span>
          </div>
          <button className="og-btn og-btn-primary og-rail-cta" onClick={ready ? submit : undefined} disabled={!ready}>
            {ready ? 'make my bouquet →' : `${remaining} to go`}
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
              <>
                {q.inputType === 'multi_select' && (
                  <p className="og-multi-hint">select all that apply</p>
                )}
                <div className="og-options">
                  {(q.options || [])
                    .filter(opt => !(q.key === 'music_era' && opt.rawValue === 'no_preference'))
                    .map(opt => {
                    const active = q.inputType === 'multi_select'
                      ? Array.isArray(answers[q.key]) && answers[q.key].includes(opt.rawValue)
                      : answers[q.key] === opt.rawValue;
                    const bleed = bleedKey && bleedKey.startsWith(`${q.key}-${opt.rawValue}-`);
                    return (
                      <button key={opt.rawValue} className={`og-option ${active ? 'is-active' : ''} ${bleed ? 'is-bleeding' : ''}`} onClick={() => select(q, opt.rawValue)}>
                        <span className="og-bleed" aria-hidden="true" />
                        <div className="og-option-wave-frame">
                          <Waveform energy={HS.getEnergy(opt.rawValue)} width={80} height={26} color={active ? 'var(--accent)' : 'var(--sage)'} strokeWidth={active ? 1.6 : 1.3} />
                        </div>
                        <div className="og-option-text">
                          <span className="og-option-label">{opt.label.toLowerCase()}</span>
                          <span className="og-option-copy">{HS.copyFor(opt.rawValue).toLowerCase()}</span>
                        </div>
                        {q.inputType === 'multi_select' && (
                          <span className={`og-multi-check ${active ? 'is-checked' : ''}`} aria-hidden="true">
                            {active ? '✓' : '○'}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </section>
        ))}
        <button className="og-btn og-btn-primary og-end-cta" onClick={ready ? submit : undefined} disabled={!ready}>
          {ready ? 'make my bouquet →' : `${remaining} to go`}
        </button>
      </div>
    </div>
  );
}

/* ── Mood sigil — the hand-drawn glyph that draws itself in ─── */
function MoodSigil({ mood, drawIn = true, size }) {
  const m = (mood || 'calm').toLowerCase();
  const cls = `og-sigil ${drawIn ? 'is-drawing' : ''}`;
  const baseProps = { viewBox: '0 0 240 240', className: cls, 'aria-hidden': 'true', ...(size ? { width: size, height: size } : {}) };

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
    <g style={{ transformOrigin: '120px 120px', animation: 'ogOrbit 16s linear infinite' }}>
      {Array.from({ length: 12 }).map((_, i) => {
        const a = (i / 12) * Math.PI * 2;
        return <line key={i} className="og-stroke" pathLength="100"
          x1={120 + Math.cos(a) * 36} y1={120 + Math.sin(a) * 36}
          x2={120 + Math.cos(a) * 80} y2={120 + Math.sin(a) * 80} />;
      })}
    </g>
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
/* ── Group "play along" sync ───────────────────────────────
 * On the results screen of a group session every device keeps a WebSocket
 * open. The host is the DJ: their player state is streamed to the backend
 * and fanned out to the group. Devices in "play along" mode mirror it;
 * "solo" devices ignore it and play independently. Toggle is per-person.
 */
function useGroupPlayAlong(groupCtx, tracks, moodLabel) {
  const player = usePlayer();
  const isHost = groupCtx?.role === 'host';
  // Everyone starts synced — the point of a group session is shared
  // listening. Either side can break off into "solo" at any time.
  const [mode, setMode] = useState('along');

  // Latest-value refs so the WebSocket handlers (stable, dep-free) never
  // read stale state. Assigned on every render — idempotent, so it's safe.
  const wsRef = useRef(null);
  const playerRef = useRef(player);
  const tracksRef = useRef(tracks);
  const moodRef = useRef(moodLabel);
  const modeRef = useRef(mode);
  const isHostRef = useRef(isHost);
  playerRef.current = player;
  tracksRef.current = tracks;
  moodRef.current = moodLabel;
  modeRef.current = mode;
  isHostRef.current = isHost;

  // Guest: snap the local player onto the host's broadcast state.
  const applyRemoteState = useCallback((state) => {
    if (isHostRef.current) return;            // the host *is* the source
    if (modeRef.current !== 'along') return;  // this listener went solo
    const p = playerRef.current;
    const tk = tracksRef.current;
    if (!tk || tk.length === 0) return;
    if (!state.active) return;                // host isn't DJ-ing — stay put

    const idx = Math.max(0, Math.min(state.trackIndex | 0, tk.length - 1));
    const onGroupQueue = p.queue.length > 0 && p.queue[0]?.id === tk[0]?.id;
    if (!onGroupQueue) {
      // First sync — load the blended playlist. The toggle/play click that
      // got us here counts as the user gesture that unlocks audio.
      p.loadPlaylist(tk, idx, moodRef.current, '#C26F3C');
    } else if (p.currentIndex !== idx) {
      p.jumpTo(idx);
    }
    // Mirror the host's exact play/pause (absolute, not a toggle — the
    // loads above optimistically start playback, so force the real value).
    p.setPlaying(state.isPlaying);

    // Re-seek only on audible drift, so playback doesn't stutter on every
    // heartbeat. Until metadata loads, duration is 0 and we let it ride.
    if (p.duration > 0 && typeof p.seekTo === 'function') {
      const localPos = p.progress * p.duration;
      if (Math.abs(localPos - state.positionSeconds) > 2) {
        p.seekTo(Math.min(1, Math.max(0, state.positionSeconds / p.duration)));
      }
    }
  }, []);

  // Host: push the current player state to the group.
  const sendControl = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !isHostRef.current) return;
    const p = playerRef.current;
    const tk = tracksRef.current;
    const onGroupQueue = p.queue.length > 0 && tk.length > 0 && p.queue[0]?.id === tk[0]?.id;
    ws.send(JSON.stringify({
      type: 'playback_control',
      payload: {
        trackIndex: onGroupQueue ? p.currentIndex : 0,
        isPlaying: !!p.isPlaying,
        positionSeconds: p.duration > 0 ? p.progress * p.duration : 0,
        // Only actually DJ once we're on the blended playlist and switched on.
        active: modeRef.current === 'along' && onGroupQueue,
      },
    }));
  }, []);

  // Mode switch with side effects: a guest turning sync back on asks the
  // backend for the current state so they snap in without waiting ~3s.
  const changeMode = useCallback((next) => {
    setMode(next);
    if (!isHostRef.current && next === 'along') {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify({ type: 'request_playback_state' })); } catch (_) {}
      }
    }
  }, []);

  // One WebSocket for the whole results screen.
  useEffect(() => {
    if (!groupCtx) return;
    let cancelled = false;
    let ws = null;
    let reconnectTimer = null;
    const connect = () => {
      if (cancelled) return;
      ws = new WebSocket(API.groupSessionSocketUrl(groupCtx.id, groupCtx.participantId));
      wsRef.current = ws;
      ws.onopen = () => {
        if (cancelled) return;
        if (isHostRef.current) sendControl();
        else if (modeRef.current === 'along') {
          try { ws.send(JSON.stringify({ type: 'request_playback_state' })); } catch (_) {}
        }
      };
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch (_) { return; }
        if (msg.type === 'playback.state' && msg.payload) applyRemoteState(msg.payload);
      };
      ws.onclose = (ev) => {
        if (wsRef.current === ws) wsRef.current = null;
        if (cancelled || ev.code === 4004) return;
        reconnectTimer = setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) { ws.onclose = null; ws.close(); }
    };
  }, [groupCtx?.id, groupCtx?.participantId, applyRemoteState, sendControl]);

  // Host: broadcast immediately on every meaningful change...
  useEffect(() => {
    if (groupCtx && isHost) sendControl();
  }, [groupCtx, isHost, mode, player.currentIndex, player.isPlaying, sendControl]);

  // ...and a steady heartbeat so listeners correct drift and seeks land.
  useEffect(() => {
    if (!groupCtx || !isHost) return;
    const id = setInterval(sendControl, 3000);
    return () => clearInterval(id);
  }, [groupCtx, isHost, sendControl]);

  return { mode, isHost, setMode: changeMode, isGroup: !!groupCtx };
}

function Results({ results, onRestart, groupCtx }) {
  const { loadPlaylist, jumpTo, isPlaying, currentTrack, queue } = usePlayer();
  const { user, openAuth } = useAuth();
  const meta = HS.moodMeta(results?.moodLabel);
  const initialTracks = results?.tracks || [];
  // Use the live queue so expanded tracks appear immediately in the list.
  // Only substitute when the queue belongs to this playlist (same first track).
  const tracks = (queue.length > 0 && initialTracks.length > 0 && queue[0]?.id === initialTracks[0]?.id)
    ? queue
    : initialTracks;
  const conf = Math.round((results?.confidence || 0) * 100);
  const avgRelevance = tracks.length
    ? tracks.reduce((s, t) => s + (t.relevanceScore || 0), 0) / tracks.length
    : 0;
  const fit = Math.min(100, Math.max(0, Math.round((avgRelevance / 2.0) * 100)));

  const [saveOpen, setSaveOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const [addOpenTrackId, setAddOpenTrackId] = useState(null);
  const [myLists, setMyLists] = useState([]);
  const [listsLoading, setListsLoading] = useState(false);
  const [listsError, setListsError] = useState(null);
  const [toast, setToast] = useState(null);

  // Group "play along" sync — no-ops for a solo (non-group) session.
  const playAlong = useGroupPlayAlong(groupCtx, tracks, results?.moodLabel);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2400); };

  const loadMyLists = async () => {
    setListsLoading(true); setListsError(null);
    try { setMyLists(await API.fetchMyPlaylists()); }
    catch (e) { setListsError(e.message); }
    finally { setListsLoading(false); }
  };

  const handlePlay = (i) => {
    // A guest hand-picking a track is taking control — drop them out of sync.
    if (playAlong.isGroup && !playAlong.isHost && playAlong.mode === 'along') {
      playAlong.setMode('solo');
    }
    if (queue.length > 0 && tracks.length > 0 && queue[0].id === tracks[0].id) {
      jumpTo(i);
    } else {
      loadPlaylist(tracks, i, results?.moodLabel, '#C26F3C');
    }
  };

  const openCreate = () => {
    if (!user) { openAuth('signin', 'sign in to save this playlist.'); return; }
    setSaveOpen(true);
  };

  const handleSave = async (name) => {
    await API.savePlaylistAs(results.playlistId, name);
    setSaved(true);
    showToast(`saved as “${name}”`);
  };

  const openAddTo = (trackId) => {
    if (!user) { openAuth('signin', 'sign in to add this song to a playlist.'); return; }
    setAddOpenTrackId(trackId);
    loadMyLists();
  };

  const handlePick = async (sp) => {
    try {
      await API.addTrackToPlaylist(sp.playlist?.id || sp.playlistId, addOpenTrackId);
      showToast(`added to “${sp.name || 'playlist'}”`);
    } catch (e) {
      showToast(e.status === 409 ? 'already in that playlist' : 'could not add');
    } finally {
      setAddOpenTrackId(null);
    }
  };

  return (
    <div className="og-results">
      <div className="og-r-left">
        <span className="og-eyebrow">your reading</span>
        <h1>{meta.label.toLowerCase()}.</h1>
        <p>{meta.desc}</p>
        <div className="og-stats">
          <div><dt>match</dt><dd>{conf}%</dd></div>
          <div><dt>song fit</dt><dd>{fit}%</dd></div>
          <div><dt>tracks</dt><dd>{tracks.length}</dd></div>
          <div><dt>length</dt><dd>~{Math.round(tracks.length * 4)}m</dd></div>
        </div>
        <div className="og-r-cta">
          <button className="og-btn og-btn-primary" onClick={() => handlePlay(0)}>play the bouquet ▸</button>
          <button className="og-btn og-btn-ghost" onClick={openCreate} disabled={saved}>
            {saved ? 'saved ✓' : '+ create playlist'}
          </button>
          <button className="og-btn og-btn-ghost" onClick={onRestart}>start a new one</button>
        </div>

        {playAlong.isGroup && (
          <div className="og-pa">
            <div className="og-pa-row">
              <span className="og-pa-label">
                {playAlong.isHost ? '🎧 dj mode' : '🎧 play along'}
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={playAlong.mode === 'along'}
                aria-label={playAlong.isHost ? 'DJ mode' : 'Play along'}
                className={`og-pa-switch ${playAlong.mode === 'along' ? 'is-on' : ''}`}
                onClick={() => playAlong.setMode(playAlong.mode === 'along' ? 'solo' : 'along')}
              >
                <span className="og-pa-knob" />
              </button>
            </div>
            <p className="og-pa-hint">
              {playAlong.isHost
                ? (playAlong.mode === 'along'
                    ? 'the group is hearing what you play.'
                    : 'playing solo — flip on to dj for everyone.')
                : (playAlong.mode === 'along'
                    ? 'in sync with the host · pick a track to go solo.'
                    : 'playing on your own.')}
            </p>
          </div>
        )}
      </div>
      <div className="og-r-right">
        <div className="og-tl-head"><span>nº</span><span>track</span><span>artist</span><span>lang</span><span>time</span><span></span></div>
        {tracks.map((t, i) => {
          const active = currentTrack && currentTrack.id === t.id;
          return (
            <div key={t.id || i} className={`og-track ${active ? 'is-active' : ''}`}>
              <button className="og-track-main" onClick={() => handlePlay(i)}>
                <span className="og-tr-n">{String(i + 1).padStart(2, '0')}</span>
                <span className="og-tr-t">{t.title}{active && <em> · {isPlaying ? 'playing' : 'paused'}</em>}</span>
                <span className="og-tr-a">{t.artistId?.name || t.artistName}</span>
                <span className="og-tr-l">{t.language}</span>
                <span className="og-tr-d">{t.durationMinutes}</span>
              </button>
              <button
                className="og-tr-add"
                title="add to a saved playlist"
                onClick={(e) => { e.stopPropagation(); openAddTo(t.id); }}
              >+</button>
            </div>
          );
        })}
      </div>

      <SavePlaylistModal
        open={saveOpen}
        defaultName={`${(results?.moodLabel || 'my').toLowerCase()} · ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }).toLowerCase()}`}
        onClose={() => setSaveOpen(false)}
        onSave={handleSave}
      />
      <AddToPlaylistPopover
        open={addOpenTrackId !== null}
        loading={listsLoading}
        playlists={myLists}
        error={listsError}
        onClose={() => setAddOpenTrackId(null)}
        onPick={handlePick}
      />
      {toast && <div className="og-toast">{toast}</div>}
    </div>
  );
}

/* ── My Playlists view ─────────────────────────────────── */
function MyPlaylists({ onBack }) {
  const player = usePlayer();
  const { loadPlaylist, togglePlay } = player;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [openTracks, setOpenTracks] = useState([]);
  const [tracksLoading, setTracksLoading] = useState(false);
  const [playingId, setPlayingId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [deletingId, setDeletingId] = useState(null);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [busy, setBusy] = useState(false);

  // Close the kebab menu on any outside click
  useEffect(() => {
    if (!menuOpenId) return;
    const close = () => setMenuOpenId(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [menuOpenId]);

  const beginRename = (sp) => { setRenamingId(sp.id); setRenameValue(sp.name || ''); };
  const cancelRename = () => { setRenamingId(null); setRenameValue(''); };
  const submitRename = async () => {
    const name = renameValue.trim();
    if (!name || !renamingId) return;
    setBusy(true);
    try {
      const updated = await API.renameSavedPlaylist(renamingId, name);
      setItems(prev => prev.map(it => it.id === renamingId ? { ...it, name: updated.name ?? name } : it));
      cancelRename();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  const removeTrack = async (sp, track) => {
    const pid = sp.playlist?.id || sp.playlistId;
    if (!pid || !track?.id) return;
    setBusy(true);
    try {
      await API.removeTrackFromPlaylist(pid, track.id);
      setOpenTracks(prev => prev.filter(t => t.id !== track.id));
      setItems(prev => prev.map(it =>
        it.id === sp.id
          ? { ...it, playlist: { ...(it.playlist || {}), trackCount: Math.max(0, (it.playlist?.trackCount || 0) - 1) } }
          : it
      ));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const confirmDelete = async () => {
    if (!deletingId) return;
    setBusy(true);
    try {
      await API.deleteSavedPlaylist(deletingId);
      setItems(prev => prev.filter(it => it.id !== deletingId));
      if (openId === deletingId) { setOpenId(null); setOpenTracks([]); }
      if (playingId === deletingId) setPlayingId(null);
      setDeletingId(null);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await API.fetchMyPlaylists();
        if (!cancelled) { setItems(data); setLoading(false); }
      } catch (e) {
        if (!cancelled) { setError(e.message); setLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const openOne = async (sp) => {
    const pid = sp.playlist?.id || sp.playlistId;
    setOpenId(sp.id);
    setTracksLoading(true);
    try {
      const rows = await API.fetchPlaylistTracks(pid);
      setOpenTracks(rows.map(t => t.track));
    } catch (e) { setError(e.message); }
    finally { setTracksLoading(false); }
  };

  const playSaved = async (sp, idx = 0) => {
    const pid = sp.playlist?.id || sp.playlistId;
    try {
      const rows = await API.fetchPlaylistTracks(pid);
      loadPlaylist(rows.map(t => t.track), idx, sp.playlist?.moodLabel || '', '#C26F3C');
      setPlayingId(sp.id);
    } catch (e) { setError(e.message); }
  };

  const handlePlayClick = (sp) => {
    if (playingId === sp.id && player.hasQueue) {
      togglePlay();
    } else {
      playSaved(sp, 0);
    }
  };

  const playLabel = (sp) => {
    if (playingId === sp.id && player.hasQueue) {
      return player.isPlaying ? 'playing ❚❚' : 'paused ▸';
    }
    return 'play ▸';
  };

  if (loading) return <OrbitalLoader label="opening your shelf…" />;
  if (error) return <div className="og-loading"><p>{error}</p></div>;

  // Detail view: sidebar of all playlists + viewed playlist's tracks on the right
  if (openId) {
    const sp = items.find(i => i.id === openId);
    if (sp) {
      const moodLabel = sp.playlist?.moodLabel || '';
      const meta = HS.moodMeta(moodLabel);
      const tracks = openTracks;
      const trackCount = tracks.length || sp.playlist?.trackCount || 0;
      return (
        <div className="og-mylists og-mylists-detail">
          <div className="og-mld-layout">
            <aside className="og-mld-sidebar">
              <div className="og-mld-sidebar-head">
                <span className="og-eyebrow">your shelf</span>
                <button className="og-btn og-btn-ghost og-btn-sm" onClick={onBack}>← home</button>
              </div>
              <div className="og-mld-list">
                {items.map(it => {
                  const isOpen = it.id === openId;
                  const isPlayingThis = playingId === it.id && player.hasQueue;
                  return (
                    <div
                      key={it.id}
                      className={`og-mld-item ${isOpen ? 'is-open' : ''} ${isPlayingThis ? 'is-playing' : ''}`}
                      onClick={() => openOne(it)}
                    >
                      <div className="og-mld-item-info">
                        <span className="og-mld-item-name">{it.name || 'untitled'}</span>
                        <span className="og-mld-item-meta">
                          {(it.playlist?.moodLabel || '—')} · {it.playlist?.trackCount || 0}
                        </span>
                      </div>
                      <button
                        className={`og-pp og-mld-item-play ${isPlayingThis ? 'is-playing' : ''}`}
                        onClick={(e) => { e.stopPropagation(); handlePlayClick(it); }}
                      >
                        {isPlayingThis && player.isPlaying ? '❚❚' : '▶'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </aside>
            <section className="og-mld-main">
              <header className="og-mld-header">
                <div className="og-mld-header-text">
                  <span className="og-eyebrow">{(meta.label || '—').toLowerCase()}</span>
                  {renamingId === sp.id ? (
                    <input
                      autoFocus
                      className="og-ml-rename-input og-mld-rename-input"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') submitRename(); if (e.key === 'Escape') cancelRename(); }}
                      disabled={busy}
                    />
                  ) : (
                    <h1>{(sp.name || meta.label || 'playlist').toLowerCase()}.</h1>
                  )}
                  <span className="og-mld-header-meta">
                    {trackCount} tracks · ~{Math.round(trackCount * 4)}m · {(meta.label || '—').toLowerCase()}
                  </span>
                </div>
                <div className="og-mld-header-cta">
                  {renamingId === sp.id ? (
                    <>
                      <button className="og-btn og-btn-primary og-btn-sm" onClick={submitRename} disabled={busy || !renameValue.trim()}>save</button>
                      <button className="og-btn og-btn-ghost og-btn-sm" onClick={cancelRename} disabled={busy}>cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="og-btn og-btn-primary og-btn-sm" onClick={() => handlePlayClick(sp)}>{playLabel(sp)}</button>
                      <div className="og-ml-menu-wrap" onClick={(e) => e.stopPropagation()}>
                        <button
                          className="og-ml-menu-btn"
                          onClick={() => setMenuOpenId(menuOpenId === sp.id ? null : sp.id)}
                          aria-label="more actions"
                        >⋯</button>
                        {menuOpenId === sp.id && (
                          <div className="og-ml-menu og-ml-menu-right">
                            <button className="og-ml-menu-item" onClick={() => { setMenuOpenId(null); beginRename(sp); }}>rename</button>
                            <button className="og-ml-menu-item og-ml-menu-danger" onClick={() => { setMenuOpenId(null); setDeletingId(sp.id); }}>delete</button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </header>
              <div className="og-mld-tracks">
                <div className="og-tl-head"><span>nº</span><span>track</span><span>artist</span><span>lang</span><span>time</span><span></span></div>
                {tracksLoading ? (
                  <p style={{ padding: '1rem', color: 'var(--ink-soft)' }}>loading…</p>
                ) : tracks.map((t, i) => {
                  const active = player.currentTrack && player.currentTrack.id === t.id;
                  return (
                    <div key={t.id || i} className={`og-track ${active ? 'is-active' : ''}`}>
                      <button className="og-track-main" onClick={() => playSaved(sp, i)}>
                        <span className="og-tr-n">{String(i + 1).padStart(2, '0')}</span>
                        <span className="og-tr-t">{t.title}{active && <em> · {player.isPlaying ? 'playing' : 'paused'}</em>}</span>
                        <span className="og-tr-a">{t.artistId?.name || t.artistName}</span>
                        <span className="og-tr-l">{t.language}</span>
                        <span className="og-tr-d">{t.durationMinutes}</span>
                      </button>
                      <button
                        className="og-tr-remove"
                        title="remove from playlist"
                        aria-label="remove from playlist"
                        onClick={(e) => { e.stopPropagation(); removeTrack(sp, t); }}
                        disabled={busy}
                      >×</button>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
          <DeleteConfirmModal
            open={!!deletingId}
            busy={busy}
            name={items.find(i => i.id === deletingId)?.name || 'this playlist'}
            onCancel={() => setDeletingId(null)}
            onConfirm={confirmDelete}
          />
        </div>
      );
    }
  }

  return (
    <div className="og-mylists">
      <div className="og-ml-head">
        <span className="og-eyebrow">your shelf</span>
        <h1>my playlists.</h1>
        <p>the rooms you've saved. step back into any of them.</p>
        <button className="og-btn og-btn-ghost og-btn-sm" onClick={onBack}>← home</button>
      </div>
      {items.length === 0 ? (
        <div className="og-ml-empty">
          <p>nothing here yet — take a session and press <em>create playlist</em>.</p>
        </div>
      ) : (
        <div className="og-ml-grid">
          {items.map(sp => {
            const isPlayingThis = playingId === sp.id && player.hasQueue;
            const isRenaming = renamingId === sp.id;
            return (
              <div key={sp.id} className={`og-ml-card ${isPlayingThis ? 'is-playing' : ''}`}>
                <div className="og-ml-card-top">
                  <div className="og-ml-card-info">
                    {isRenaming ? (
                      <input
                        autoFocus
                        className="og-ml-rename-input"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') submitRename(); if (e.key === 'Escape') cancelRename(); }}
                        disabled={busy}
                      />
                    ) : (
                      <h3>{sp.name || 'untitled'}</h3>
                    )}
                    <span className="og-ml-meta">
                      {(sp.playlist?.moodLabel || '—')} · {sp.playlist?.trackCount || 0} tracks
                    </span>
                  </div>
                  <button
                    className={`og-pp og-ml-card-play ${isPlayingThis ? 'is-playing' : ''}`}
                    onClick={() => handlePlayClick(sp)}
                    aria-label={playLabel(sp)}
                  >
                    {isPlayingThis && player.isPlaying ? '❚❚' : '▶'}
                  </button>
                  <div className="og-ml-menu-wrap" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="og-ml-menu-btn"
                      onClick={() => setMenuOpenId(menuOpenId === sp.id ? null : sp.id)}
                      aria-label="more actions"
                    >⋯</button>
                    {menuOpenId === sp.id && (
                      <div className="og-ml-menu">
                        <button className="og-ml-menu-item" onClick={() => { setMenuOpenId(null); beginRename(sp); }}>rename</button>
                        <button className="og-ml-menu-item og-ml-menu-danger" onClick={() => { setMenuOpenId(null); setDeletingId(sp.id); }}>delete</button>
                      </div>
                    )}
                  </div>
                </div>
                <div className="og-ml-card-actions">
                  {isRenaming ? (
                    <>
                      <button className="og-btn og-btn-primary og-btn-sm" onClick={submitRename} disabled={busy || !renameValue.trim()}>save</button>
                      <button className="og-btn og-btn-ghost og-btn-sm" onClick={cancelRename} disabled={busy}>cancel</button>
                    </>
                  ) : (
                    <button className="og-btn og-btn-ghost og-btn-sm" onClick={() => openOne(sp)}>view</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <DeleteConfirmModal
        open={!!deletingId}
        busy={busy}
        name={items.find(i => i.id === deletingId)?.name || 'this playlist'}
        onCancel={() => setDeletingId(null)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}

function DeleteConfirmModal({ open, busy, name, onCancel, onConfirm }) {
  if (!open) return null;
  return (
    <div className="og-modal-backdrop" onClick={onCancel}>
      <div className="og-modal" onClick={(e) => e.stopPropagation()}>
        <h3>delete playlist?</h3>
        <p className="og-modal-sub">“{name}” will be permanently removed from your shelf. this can't be undone.</p>
        <div className="og-modal-actions">
          <button className="og-btn og-btn-ghost" onClick={onCancel} disabled={busy}>cancel</button>
          <button className="og-btn og-btn-primary og-modal-danger" onClick={onConfirm} disabled={busy}>{busy ? 'deleting…' : 'delete'}</button>
        </div>
      </div>
    </div>
  );
}

/* ── Player strip ──────────────────────────────────────── */
function PlayerStrip({ onNewSession, playlistId }) {
  const { currentTrack: track, queue, currentIndex, isPlaying, isLoadingAudio, togglePlay, playNext, playPrevious, closePlayer, appendToQueue, moodLabel, progress, seekTo } = usePlayer();
  const { user, openAuth } = useAuth();
  const [expanding, setExpanding] = useState(false);

  const isLastTrack = queue.length > 0 && currentIndex === queue.length - 1;

  const handleExpand = async () => {
    if (!playlistId || expanding) return;
    setExpanding(true);
    try {
      const currentCount = queue.length;
      await API.expandPlaylist(playlistId);
      const newTracks = await API.fetchPlaylistTracks(playlistId, { offset: currentCount, limit: 40 });
      appendToQueue(newTracks.map(t => t.track));
    } catch (e) {
      console.error('expand failed', e);
    } finally {
      setExpanding(false);
    }
  };

  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => setTick(t => t + 1), 60);
    return () => clearInterval(id);
  }, [isPlaying]);

  // All hooks must be called before any early return (Rules of Hooks)
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

  if (!track || !queue.length) return null;

  const meta = HS.moodMeta(moodLabel);

  const handleSeek = (e) => {
    if (!seekTo) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX ?? e.touches?.[0]?.clientX ?? e.changedTouches?.[0]?.clientX;
    if (clientX == null) return;
    const x = clientX - rect.left;
    seekTo(Math.max(0, Math.min(1, x / rect.width)));
  };

  const boatX = (progress || 0) * waveW;
  const boatPhase = tick / 8;
  const boatY = waveMid + Math.sin(((boatX / waveW) * n) * 0.45 + boatPhase) * 5 + Math.sin(((boatX / waveW) * n) * 0.2 + boatPhase * 0.7) * 3.5;

  const playIcon = isLoadingAudio ? '···' : isPlaying ? '❚❚' : '▶';

  return (
    <div className="og-player">
      <div className="og-player-glow" />
      {isLastTrack && (
        <div className="og-player-end">
          <span className="og-player-end-label">last track</span>
          <div className="og-player-end-actions">
            {user ? (
              <button
                className="og-btn og-btn-primary"
                onClick={handleExpand}
                disabled={expanding}
              >
                {expanding ? 'adding…' : '+ 40 more ▸'}
              </button>
            ) : (
              <button
                className="og-btn og-btn-primary"
                onClick={() => openAuth('signin', 'Sign in to unlock 40 more tracks from this playlist.')}
              >
                sign in for more ▸
              </button>
            )}
            <button className="og-btn og-btn-ghost" onClick={onNewSession}>new session</button>
          </div>
        </div>
      )}
      <div className="og-player-inner">
        <div className="og-player-mood"><span className="og-pdot" />{(meta?.label || moodLabel || 'playing').toLowerCase()}</div>
        <div className="og-player-track">
          <span className="og-pt">{track.title}</span>
          <span className="og-pa">{isLoadingAudio ? 'finding on JioSaavn…' : (track.artistId?.name || track.artistName)}</span>
        </div>

        <svg viewBox={`0 0 ${waveW} ${waveH}`} preserveAspectRatio="none" height={waveH} className="og-player-wave" onClick={handleSeek} onTouchEnd={handleSeek} style={{ cursor: 'pointer', overflow: 'visible', touchAction: 'manipulation', width: '100%', maxWidth: waveW + 'px' }}>
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
          <button onClick={playPrevious} disabled={currentIndex === 0 || isLoadingAudio}>‹‹</button>
          <button onClick={togglePlay} className="og-pp" disabled={isLoadingAudio}>{playIcon}</button>
          <button onClick={playNext} disabled={currentIndex >= queue.length - 1 || isLoadingAudio}>››</button>
        </div>
        <div className="og-player-meta"><span>{currentIndex + 1}/{queue.length}</span><button className="og-pclose" onClick={closePlayer}>×</button></div>
      </div>
    </div>
  );
}

/* ── Group: create / join modals ───────────────────────── */
function GroupNameModal({ open, title, cta, requireCode, initialCode = '', onClose, onSubmit }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState(initialCode);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => { if (open) { setName(''); setCode(initialCode || ''); setErr(null); setBusy(false); } }, [open, initialCode]);
  if (!open) return null;

  const go = async (e) => {
    e?.preventDefault?.();
    if (busy) return;
    if (!name.trim()) { setErr('your name, please'); return; }
    if (requireCode && !code.trim()) { setErr('enter the group code'); return; }
    setBusy(true); setErr(null);
    try {
      await onSubmit({ name: name.trim(), code: code.trim().toUpperCase() });
    } catch (e) {
      setErr(e.message || 'could not continue');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="og-modal-backdrop" onClick={busy ? undefined : onClose}>
      <form className="og-modal" onClick={e => e.stopPropagation()} onSubmit={go}>
        <h3>{title}</h3>
        <span className="og-modal-hint">everyone needs to be on the same wifi to listen together</span>
        {requireCode && (
          <input
            autoFocus
            className="og-modal-input og-modal-code"
            placeholder="ABC123"
            value={code}
            maxLength={8}
            onChange={e => setCode(e.target.value.toUpperCase())}
          />
        )}
        <input
          autoFocus={!requireCode}
          className="og-modal-input"
          placeholder="your name (or a nickname)"
          value={name}
          maxLength={64}
          onChange={e => setName(e.target.value)}
        />
        {err && <span className="og-modal-err">{err}</span>}
        <div className="og-modal-actions">
          <button type="button" className="og-btn og-btn-ghost" onClick={onClose} disabled={busy}>cancel</button>
          <button type="submit" className="og-btn og-btn-primary" disabled={busy}>{busy ? '…' : cta}</button>
        </div>
      </form>
    </div>
  );
}

/* ── Group lobby ───────────────────────────────────────── */
function GroupLobby({ group: initialGroup, role, participantId, onTakeSurvey, onPlaylistReady, onLeave }) {
  const [group, setGroup] = useState(initialGroup);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  // Live lobby updates over a WebSocket (Django Channels). The backend pushes
  // the full session snapshot on connect and again whenever someone joins,
  // marks ready, or the host generates the playlist.
  useEffect(() => {
    if (group.status === 'generated') return;
    let cancelled = false;
    let ws = null;
    let reconnectTimer = null;

    const applySnapshot = async (fresh) => {
      if (cancelled) return;
      if (fresh.status === 'generated' && fresh.playlistId) {
        // Navigate BEFORE setGroup — otherwise the status-change re-render
        // triggers this effect's cleanup (cancelled=true) mid-await, which
        // would swallow onPlaylistReady and strand the user on the lobby.
        const tracks = await API.fetchPlaylistTracks(fresh.playlistId);
        if (cancelled) return;
        onPlaylistReady({
          moodLabel: fresh.blendedMoodLabel || fresh.playlist?.moodLabel,
          confidence: fresh.playlist?.confidence || 0,
          tracks: tracks.map(t => ({ ...t.track, relevanceScore: t.relevanceScore })),
          playlistId: fresh.playlistId,
        });
        return;
      }
      setGroup(fresh);
    };

    const connect = () => {
      if (cancelled) return;
      ws = new WebSocket(API.groupSessionSocketUrl(group.id, participantId));
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type === 'group.update' && msg.payload) applySnapshot(msg.payload);
      };
      ws.onclose = (ev) => {
        // 4004 = server rejected an unknown group; don't retry that.
        if (cancelled || ev.code === 4004) return;
        reconnectTimer = setTimeout(connect, 2000);
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) { ws.onclose = null; ws.close(); }
    };
  }, [group.id, group.status]);

  const me = group.participants?.find(p => p.id === participantId);
  const readyCount = (group.participants || []).filter(p => p.isReady).length;
  const total = group.participants?.length || 0;
  const canGenerate = role === 'host' && readyCount >= 1;
  // The phone can't reach the laptop's "localhost" — when the host opens the
  // app on localhost we discover the laptop's LAN address via a WebRTC ICE
  // candidate (the browser already knows it; we don't actually open a peer
  // connection). That hostname goes into the QR so scanning Just Works.
  const isLoopback = ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname);
  const [shareHost, setShareHost] = useState(() => localStorage.getItem('hn_share_host') || '');
  const [hostInput, setHostInput] = useState(shareHost);
  const [detecting, setDetecting] = useState(isLoopback && !shareHost);

  useEffect(() => {
    if (!isLoopback || shareHost) return;
    let cancelled = false;
    (async () => {
      // Source 1: Vite injected the laptop's LAN IP at startup. This is the
      // reliable path because it reads os.networkInterfaces() directly on
      // the host, bypassing the browser's mDNS obfuscation entirely.
      let detected = null;
      try { detected = __LAN_IP__ || null; } catch { /* define did not run */ }
      // Source 2: fall back to WebRTC ICE if Vite didn't inject one
      // (e.g. running a static build, or laptop has no Wi-Fi/Ethernet up).
      if (!detected) detected = await detectLanHost();
      if (cancelled) return;
      if (detected) {
        setShareHost(detected);
        localStorage.setItem('hn_share_host', detected);
        setHostInput(detected);
      }
      setDetecting(false);
    })();
    return () => { cancelled = true; };
  }, [isLoopback, shareHost]);

  const shareOrigin = (isLoopback && shareHost)
    ? `${window.location.protocol}//${shareHost}${window.location.port ? ':' + window.location.port : ''}`
    : window.location.origin;
  const joinUrl = `${shareOrigin}/?join=${group.code}`;

  const saveShareHost = (raw) => {
    const cleaned = (raw || '').trim().replace(/^https?:\/\//, '').replace(/\/.*$/, '').replace(/:\d+$/, '');
    setShareHost(cleaned);
    if (cleaned) localStorage.setItem('hn_share_host', cleaned);
    else localStorage.removeItem('hn_share_host');
  };

  const copyCode = () => {
    try { navigator.clipboard.writeText(group.code); } catch (_) {}
  };

  const handleGenerate = async () => {
    setGenerating(true); setError(null);
    try {
      const fresh = await API.generateGroupPlaylist(group.id);
      if (fresh?.status === 'generated' && fresh.playlistId) {
        const tracks = await API.fetchPlaylistTracks(fresh.playlistId);
        onPlaylistReady({
          moodLabel: fresh.blendedMoodLabel || fresh.playlist?.moodLabel,
          confidence: fresh.playlist?.confidence || 0,
          tracks: tracks.map(t => ({ ...t.track, relevanceScore: t.relevanceScore })),
          playlistId: fresh.playlistId,
        });
        return;
      }
      setGroup(fresh);
      setGenerating(false);
    }
    catch (e) { setError(e.message); setGenerating(false); }
  };

  return (
    <div className="og-grouplobby">
      <div className="og-gl-head">
        <span className="og-eyebrow">a session for the room</span>
        <h1>listen <em>together</em>.</h1>
        <p>each person answers their own survey on their own device, and we blend the readings into one playlist.</p>
      </div>

      <div className="og-gl-body">
        <div className="og-gl-card og-gl-code-card">
          <span className="og-gl-label">join code</span>
          <div className="og-gl-code">{group.code}</div>
          <button className="og-btn og-btn-ghost og-btn-sm" onClick={copyCode}>copy code</button>
          <div className="og-gl-qr" title={`Scan to join ${group.code}`}>
            <QRCodeSVG
              value={joinUrl}
              size={180}
              level="M"
              bgColor="transparent"
              fgColor="var(--ink)"
            />
          </div>
          {isLoopback && detecting && (
            <span className="og-gl-aside">finding your LAN address…</span>
          )}
          {isLoopback && !detecting && !shareHost && (
            <div className="og-gl-lan-warn">
              <strong>couldn&rsquo;t auto-detect your LAN address.</strong>
              <span>type your laptop&rsquo;s LAN IP so the QR points there:</span>
              <div className="og-gl-lan-row">
                <input
                  className="og-modal-input"
                  placeholder="192.168.1.42"
                  value={hostInput}
                  onChange={e => setHostInput(e.target.value)}
                />
                <button className="og-btn og-btn-primary og-btn-sm" onClick={() => saveShareHost(hostInput)}>use</button>
              </div>
              <span className="og-gl-aside">find it with <code>ipconfig</code> (Windows) or <code>ifconfig</code> (mac/linux).</span>
            </div>
          )}
          {shareHost && (
            <span className="og-gl-aside">
              QR → <code>{shareHost}</code> ·{' '}
              <button className="og-link" onClick={() => saveShareHost('')}>change</button>
            </span>
          )}
          {!isLoopback && (
            <span className="og-gl-aside">scan, or go to /?join={group.code}</span>
          )}
        </div>

        <div className="og-gl-card og-gl-people">
          <span className="og-gl-label">in the room · {readyCount}/{total} ready</span>
          <ul className="og-gl-list">
            {(group.participants || []).map(p => (
              <li key={p.id} className={`${p.isReady ? 'is-ready' : ''} ${p.id === participantId ? 'is-me' : ''}`}>
                <span className="og-gl-dot" aria-hidden="true" />
                <span className="og-gl-name">{p.displayName}{p.isHost && ' · host'}{p.id === participantId && ' · you'}</span>
                <span className="og-gl-mood">{p.isReady ? (p.moodLabel || 'ready') : 'taking survey…'}</span>
              </li>
            ))}
          </ul>

          <div className="og-gl-actions">
            {me && !me.isReady && (
              <button className="og-btn og-btn-primary" onClick={onTakeSurvey}>take your survey ▸</button>
            )}
            {me && me.isReady && group.status !== 'generated' && (
              <span className="og-gl-aside">you&rsquo;re ready — waiting for the rest of the room.</span>
            )}
            {role === 'host' && (
              <button
                className="og-btn og-btn-primary"
                disabled={!canGenerate || generating}
                onClick={handleGenerate}
                title={canGenerate ? '' : 'waiting for someone to finish their survey'}
              >
                {generating ? 'blending…' : (canGenerate ? 'blend & play ▸' : 'waiting…')}
              </button>
            )}
            <button className="og-btn og-btn-ghost og-btn-sm" onClick={onLeave}>leave</button>
          </div>
          {error && <span className="og-modal-err">{error}</span>}
        </div>
      </div>
    </div>
  );
}

/* ── Root ──────────────────────────────────────────────── */
function HarmonicOrganic({ density = 'airy', palette = 'sand', typeStyle = 'editorial' }) {
  const [view, setView] = useState('home');
  const [results, setResults] = useState(null);
  const [groupCtx, setGroupCtx] = useState(null);   // { id, code, role, participantId }
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [showJoinGroup, setShowJoinGroup] = useState(false);
  const [joinCodeSeed, setJoinCodeSeed] = useState('');
  const [showGuestPrompt, setShowGuestPrompt] = useState(false);
  const [farewell, setFarewell] = useState(null);
  const { closePlayer } = usePlayer();
  const { user, authReady, openAuth, logout } = useAuth();

  const handleStartSession = () => {
    if (authReady && !user) { setShowGuestPrompt(true); return; }
    setView('mood');
  };

  const handleLogout = async () => {
    const name = user?.firstName;
    closePlayer();
    setResults(null);
    setGroupCtx(null);
    setView('home');
    try { await logout(); } catch (_) { /* swallow — UI has already navigated */ }
    setFarewell(name ? `see you soon, ${name} ✿` : 'see you soon ✿');
    setTimeout(() => setFarewell(null), 2800);
  };

  const onComplete = (data) => {
    if (data?.groupReturn) {
      // Group survey just submitted — return to the lobby.
      setView('group-lobby');
      return;
    }
    setResults(data);
    setView('results');
  };

  const handleNewSession = () => {
    closePlayer();
    setResults(null);
    setGroupCtx(null);
    setView('home');
  };

  const handleCreateGroup = async ({ name }) => {
    const { groupSession, participantId } = await API.createGroupSession(name);
    setGroupCtx({
      id: groupSession.id,
      code: groupSession.code,
      role: 'host',
      participantId,
      initial: groupSession,
    });
    setShowCreateGroup(false);
    setView('group-lobby');
  };

  const handleJoinGroup = async ({ name, code }) => {
    const { groupSession, participantId } = await API.joinGroupSession(code, name);
    setGroupCtx({
      id: groupSession.id,
      code: groupSession.code,
      role: 'guest',
      participantId,
      initial: groupSession,
    });
    setShowJoinGroup(false);
    setView('group-lobby');
  };

  // Auto-open the join modal if the URL has ?join=CODE
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('join');
    if (code) {
      setJoinCodeSeed(code.toUpperCase());
      setShowJoinGroup(true);
    }
  }, []);

  return (
    <div className={`og-shell density-${density} palette-${palette} type-${typeStyle}`}>
      <AmbientLayer />
      <PaperBackdrop />
      <Header
        view={view}
        onHome={() => { setView('home'); setResults(null); }}
        onMyPlaylists={() => setView('mylists')}
        onConcertMode={() => setView('concert')}
        onLogout={handleLogout}
      />
      <main className={`og-main view-${view}`}>
        {view === 'home' && (
          <Landing
            onStart={handleStartSession}
            onStartGroup={() => setShowCreateGroup(true)}
            onJoinGroup={() => setShowJoinGroup(true)}
            onConcertMode={() => setView('concert')}
          />
        )}
        {view === 'mood' && (
          <MoodCard
            onComplete={onComplete}
            onGuestLimit={() => setView('home')}
            groupContext={groupCtx ? { groupId: groupCtx.id, participantId: groupCtx.participantId } : null}
          />
        )}
        {view === 'results' && (
          <Results
            results={results}
            groupCtx={groupCtx}
            onRestart={() => { setView('home'); setResults(null); setGroupCtx(null); }}
          />
        )}
        {view === 'mylists' && <MyPlaylists onBack={() => setView('home')} />}
        {view === 'concert' && <ConcertMode onBack={() => setView('home')} />}
        {view === 'group-lobby' && groupCtx && (
          <GroupLobby
            group={groupCtx.initial}
            role={groupCtx.role}
            participantId={groupCtx.participantId}
            onTakeSurvey={() => setView('mood')}
            onPlaylistReady={(data) => { setResults(data); setView('results'); }}
            onLeave={() => { setGroupCtx(null); setView('home'); }}
          />
        )}
      </main>
      <PlayerStrip onNewSession={handleNewSession} playlistId={results?.playlistId} />
      <MusicPlayer />
      <AuthModal />
      <GroupNameModal
        open={showCreateGroup}
        title="start a group session"
        cta="create room"
        requireCode={false}
        onClose={() => setShowCreateGroup(false)}
        onSubmit={handleCreateGroup}
      />
      <GroupNameModal
        open={showJoinGroup}
        title="join a session"
        cta="join room"
        requireCode={true}
        initialCode={joinCodeSeed}
        onClose={() => { setShowJoinGroup(false); setJoinCodeSeed(''); }}
        onSubmit={handleJoinGroup}
      />
      <GuestSessionPrompt
        open={showGuestPrompt}
        onClose={() => setShowGuestPrompt(false)}
        onContinue={() => { setShowGuestPrompt(false); setView('mood'); }}
        onSignIn={() => { setShowGuestPrompt(false); openAuth('signin'); }}
        onSignUp={() => { setShowGuestPrompt(false); openAuth('signup'); }}
      />
      {farewell && <div className="og-toast og-toast-farewell">{farewell}</div>}
    </div>
  );
}

function GuestSessionPrompt({ open, onClose, onContinue, onSignIn, onSignUp }) {
  if (!open) return null;
  return (
    <div className="og-modal-backdrop" onClick={onClose}>
      <div className="og-modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <h3>you're not signed in</h3>
        <p className="og-modal-body">
          Sign in to save playlists, unlock full 60-track sessions, and pick up where you left off.
          You can still take the survey and listen to <em>15 songs</em> as a guest.
        </p>
        <div className="og-modal-actions og-modal-actions-stack">
          <button type="button" className="og-btn og-btn-primary" onClick={onSignIn}>sign in</button>
          <button type="button" className="og-btn og-btn-ghost" onClick={onSignUp}>create account</button>
          <button type="button" className="og-btn og-btn-ghost og-btn-sm" onClick={onContinue}>continue as guest →</button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <PlayerProvider>
        <HarmonicOrganic />
      </PlayerProvider>
    </AuthProvider>
  );
}
