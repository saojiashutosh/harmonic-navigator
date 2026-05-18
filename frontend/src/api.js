import HS from './utils/HarmonicShared';

// API calls go same-origin (e.g. /moods/..., /groups/...). Vite's dev server
// proxies those paths to Django on :8000 — see vite.config.js. This means the
// phone only ever needs to reach the Vite port; the backend stays internal.
const BASE_URL = '';

// Strip HTML entities from the user-visible string fields of a track object.
// Upstream sources (e.g. JioSaavn) occasionally serve titles like
// `From &quot;Aashiqui 2&quot;` — decode once at the API boundary so the UI
// never has to think about it.
const cleanTrack = (t) => {
  if (!t || typeof t !== 'object') return t;
  return {
    ...t,
    title: HS.decodeHtml(t.title),
    artistName: HS.decodeHtml(t.artistName),
    album: HS.decodeHtml(t.album),
    artistId: t.artistId ? { ...t.artistId, name: HS.decodeHtml(t.artistId.name) } : t.artistId,
  };
};
const cleanPlaylistTrackRow = (row) => row?.track ? { ...row, track: cleanTrack(row.track) } : row;

const JSON_HEADERS = { 'Content-Type': 'application/json' };

const getToken = () => localStorage.getItem('hn_token');

const authHeaders = () => {
  const token = getToken();
  return token ? { ...JSON_HEADERS, Authorization: `Token ${token}` } : JSON_HEADERS;
};

const storeToken = (token) => {
  if (token) localStorage.setItem('hn_token', token);
  else localStorage.removeItem('hn_token');
};

// ── Auth ──────────────────────────────────────────────────────────────────────

export const registerUser = async ({ email, password, firstName, lastName }) => {
  const res = await fetch(`${BASE_URL}/users/auth/register/`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password, firstName, lastName }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Registration failed.');
  storeToken(data.token);
  return data.user;
};

export const loginUser = async ({ email, password }) => {
  const res = await fetch(`${BASE_URL}/users/auth/login/`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Login failed.');
  storeToken(data.token);
  return data.user;
};

export const logoutUser = async () => {
  const token = getToken();
  if (token) {
    await fetch(`${BASE_URL}/users/auth/logout/`, {
      method: 'POST',
      headers: authHeaders(),
    }).catch(() => {});
  }
  storeToken(null);
};

export const fetchMe = async () => {
  const token = getToken();
  if (!token) throw new Error('No token');
  const res = await fetch(`${BASE_URL}/users/auth/me/`, { headers: authHeaders() });
  if (!res.ok) { storeToken(null); throw new Error('Session expired'); }
  return res.json();
};

// ── Moods & Playlists ─────────────────────────────────────────────────────────

export const fetchQuestions = async () => {
  const res = await fetch(`${BASE_URL}/moods/questions/?limit=100`);
  if (!res.ok) throw new Error(`Failed to fetch questions: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : data.results ?? [];
};

export const createMoodSession = async () => {
  const res = await fetch(`${BASE_URL}/moods/mood-sessions/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(data.detail || `Failed to create mood session: ${res.status}`);
    err.status = res.status;
    err.code = data.code;
    throw err;
  }
  return res.json();
};

export const submitAnswers = async (sessionId, answersMap) => {
  const answers = Object.entries(answersMap)
    .filter(([, raw_value]) => Array.isArray(raw_value) ? raw_value.length > 0 : true)
    .map(([question_key, raw_value]) => ({
      question_key,
      raw_value: raw_value ?? '',
    }));

  const res = await fetch(`${BASE_URL}/moods/mood-sessions/${sessionId}/submit/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error(`Failed to submit answers: ${res.status}`);
  return res.json();
};

export const generatePlaylist = async (moodSessionId, limit = 10) => {
  const res = await fetch(`${BASE_URL}/playlists/playlists/generate/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ moodSessionId, limit }),
  });
  if (!res.ok) throw new Error(`Failed to generate playlist: ${res.status}`);
  const data = await res.json();
  if (data && Array.isArray(data.tracks)) data.tracks = data.tracks.map(cleanTrack);
  return data;
};

export const expandPlaylist = async (playlistId) => {
  const res = await fetch(`${BASE_URL}/playlists/playlists/${playlistId}/expand/`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to expand playlist: ${res.status}`);
  return res.json();
};

/**
 * Fetch tracks for a specific playlist.
 * GET /playlists/playlist-tracks/?playlistId={id}
 * Returns: Array of playlist track objects (each includes a `track` sub-object)
 */
export const fetchPlaylistTracks = async (playlistId, { offset = 0, limit = 200 } = {}) => {
  const res = await fetch(
    `${BASE_URL}/playlists/playlist-tracks/?playlistId=${playlistId}&ordering=position&limit=${limit}&offset=${offset}`
  );
  if (!res.ok) throw new Error(`Failed to fetch playlist tracks: ${res.status}`);
  const data = await res.json();
  const rows = Array.isArray(data) ? data : data.results ?? [];
  return rows.map(cleanPlaylistTrackRow);
};

// ── Saved Playlists ───────────────────────────────────────────────────────────

export const savePlaylistAs = async (playlistId, name) => {
  const res = await fetch(`${BASE_URL}/playlists/playlists/${playlistId}/save-as/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Failed to save playlist: ${res.status}`);
  return data;
};

export const removeTrackFromPlaylist = async (playlistId, trackId) => {
  const res = await fetch(`${BASE_URL}/playlists/playlists/${playlistId}/remove-track/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ trackId }),
  });
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to remove track: ${res.status}`);
  }
};

export const addTrackToPlaylist = async (playlistId, trackId) => {
  const res = await fetch(`${BASE_URL}/playlists/playlists/${playlistId}/add-track/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ trackId }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || `Failed to add track: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
};

export const fetchMyPlaylists = async () => {
  const res = await fetch(`${BASE_URL}/playlists/saved-playlists/mine/?limit=200`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch saved playlists: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : data.results ?? [];
};

export const renameSavedPlaylist = async (savedPlaylistId, name) => {
  const res = await fetch(`${BASE_URL}/playlists/saved-playlists/${savedPlaylistId}/`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ name }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Failed to rename playlist: ${res.status}`);
  return data;
};

export const deleteSavedPlaylist = async (savedPlaylistId) => {
  const res = await fetch(`${BASE_URL}/playlists/saved-playlists/${savedPlaylistId}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to delete playlist: ${res.status}`);
  }
};

// ── Group Sessions ────────────────────────────────────────────────────────────

export const createGroupSession = async (displayName) => {
  const res = await fetch(`${BASE_URL}/groups/group-sessions/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ displayName }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Failed to create group: ${res.status}`);
  return data;  // { groupSession, participantId }
};

export const joinGroupSession = async (code, displayName) => {
  const res = await fetch(`${BASE_URL}/groups/group-sessions/join/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ code: (code || '').toUpperCase(), displayName }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Failed to join group: ${res.status}`);
  return data;  // { groupSession, participantId }
};

export const fetchGroupSession = async (groupId) => {
  const res = await fetch(`${BASE_URL}/groups/group-sessions/${groupId}/`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch group: ${res.status}`);
  return res.json();
};

export const attachMoodSessionToGroup = async (groupId, participantId, moodSessionId) => {
  const res = await fetch(`${BASE_URL}/groups/group-sessions/${groupId}/attach-session/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ participantId, moodSessionId }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Failed to attach session: ${res.status}`);
  return data;
};

export const generateGroupPlaylist = async (groupId) => {
  const res = await fetch(`${BASE_URL}/groups/group-sessions/${groupId}/generate/`, {
    method: 'POST',
    headers: authHeaders(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Failed to generate: ${res.status}`);
  return data;
};

// Live group-session WebSocket (Django Channels): lobby updates plus the
// host-driven "play along" playback sync. Same-origin so Vite's dev proxy
// forwards it to Django; the scheme tracks the page (wss:// on HTTPS). The
// participant id lets the backend tell whether this socket is the host.
export const groupSessionSocketUrl = (groupId, participantId) => {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const query = participantId ? `?participant=${encodeURIComponent(participantId)}` : '';
  return `${scheme}://${window.location.host}/ws/groups/${groupId}/${query}`;
};

/**
 * Fetch a full-quality audio stream URL from JioSaavn.
 * Pass trackId to enable DB caching — subsequent calls for the same track
 * are served from the DB instantly without hitting JioSaavn.
 */
export const fetchSaavnSearch = async (query, trackId) => {
  let url = `${BASE_URL}/playlists/saavn-search/?q=${encodeURIComponent(query)}`;
  if (trackId) url += `&track_id=${encodeURIComponent(trackId)}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  const data = await res.json();
  return data.audioUrl || null;
};
