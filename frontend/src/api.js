const BASE_URL = 'http://localhost:8000';

const headers = {
  'Content-Type': 'application/json',
};

/**
 * Fetch all active mood questions.
 * GET /moods/questions/
 */
export const fetchQuestions = async () => {
  const res = await fetch(`${BASE_URL}/moods/questions/`);
  if (!res.ok) throw new Error(`Failed to fetch questions: ${res.status}`);
  const data = await res.json();
  // Handle both array and paginated { results: [...] } responses
  return Array.isArray(data) ? data : data.results ?? [];
};

/**
 * Create a new mood session.
 * POST /moods/mood-sessions/
 * Returns: { id, moodSessionId, ... }
 */
export const createMoodSession = async () => {
  const res = await fetch(`${BASE_URL}/moods/mood-sessions/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Failed to create mood session: ${res.status}`);
  return res.json();
};

/**
 * Submit answers for a mood session.
 * POST /moods/mood-sessions/{id}/submit/
 * @param {string} sessionId - The mood session UUID
 * @param {Object} answersMap - { question_key: raw_value, ... }
 * Returns: { id, moodLabel, confidence, rawScores, moodSessionId }
 */
export const submitAnswers = async (sessionId, answersMap) => {
  const answers = Object.entries(answersMap).map(([question_key, raw_value]) => ({
    question_key,
    raw_value: raw_value ?? '',
  }));

  const res = await fetch(`${BASE_URL}/moods/mood-sessions/${sessionId}/submit/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error(`Failed to submit answers: ${res.status}`);
  return res.json();
};

/**
 * Generate a playlist from a mood session.
 * POST /playlists/playlists/generate/
 * @param {string} moodSessionId - The mood session UUID
 * @param {number} limit - Number of tracks (default 10)
 * Returns: { id, moodLabel, confidence, trackCount, status }
 */
export const generatePlaylist = async (moodSessionId, limit = 10) => {
  const res = await fetch(`${BASE_URL}/playlists/playlists/generate/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ moodSessionId, limit }),
  });
  if (!res.ok) throw new Error(`Failed to generate playlist: ${res.status}`);
  return res.json();
};

/**
 * Fetch tracks for a specific playlist.
 * GET /playlists/playlist-tracks/?playlistId={id}
 * Returns: Array of playlist track objects (each includes a `track` sub-object)
 */
export const fetchPlaylistTracks = async (playlistId) => {
  const res = await fetch(`${BASE_URL}/playlists/playlist-tracks/?playlistId=${playlistId}`);
  if (!res.ok) throw new Error(`Failed to fetch playlist tracks: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : data.results ?? [];
};
