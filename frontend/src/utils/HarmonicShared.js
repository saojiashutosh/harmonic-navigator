// Map raw answer values to "energy" 0..1 (low → high) for waveform amplitude
const ENERGY_BY_VALUE = {
  // energy_level
  drained: 0.10, low: 0.25, mid: 0.50, good: 0.75, charged: 0.95,
  // emotional_tone
  happy: 0.75, calm: 0.30, sad: 0.20, tense: 0.85, flat: 0.15, excited: 0.95,
  // mental_state
  sharp: 0.75, scattered: 0.85, drifting: 0.30, motivated: 0.85, blank: 0.20,
  // activity
  working: 0.55, exercising: 0.95, relaxing: 0.25, commuting: 0.45, social: 0.80, sleeping: 0.10,
  // playlist_goal
  focus: 0.55, relax: 0.25, uplift: 0.80, escape: 0.40, party: 0.95, sleep: 0.10,
  // language / nostalgia neutrals
  no_preference: 0.50, english: 0.55, hindi: 0.60, marathi: 0.55, punjabi: 0.85,
  instrumental: 0.35, discover_new: 0.65, old_favorites: 0.40, mix_both: 0.55,
};

function waveformPath(energy = 0.5, width = 96, height = 24, samples = 48) {
  const amp = (height / 2) * (0.25 + energy * 0.7);
  const freq = 1.6 + energy * 4.0;
  const mid = height / 2;
  let d = '';
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const x = t * width;
    const y = mid +
      Math.sin(t * freq * Math.PI * 2) * amp * 0.85 +
      Math.sin(t * freq * Math.PI * 2 * 1.7 + 1.2) * amp * 0.18;
    d += (i === 0 ? 'M' : 'L') + x.toFixed(2) + ',' + y.toFixed(2) + ' ';
  }
  return d;
}

function getEnergy(rawValue) {
  return ENERGY_BY_VALUE[rawValue] ?? 0.5;
}

function humanize(s) {
  if (!s) return '';
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

const OPTION_COPY = {
  drained: 'Soft, low and quiet',
  low: 'Gentle, present',
  mid: 'Steady, coasting',
  good: 'Sharp and ready',
  charged: 'Overflowing, electric',
  happy: 'Light and warm',
  calm: 'Centered, still',
  sad: 'Heavy and slow',
  tense: 'Restless, wired',
  flat: 'Numb, levelled',
  excited: 'Buzzing, alight',
  sharp: 'Crystal clear',
  scattered: 'Branching every way',
  drifting: 'Floating, daydreaming',
  motivated: 'Driven and certain',
  blank: 'Empty, quiet',
  working: 'Deep in the task',
  exercising: 'Moving, burning',
  relaxing: 'Winding down',
  commuting: 'On the way',
  social: 'With people',
  sleeping: 'Almost asleep',
  focus: 'Lock me in',
  relax: 'Help me unwind',
  uplift: 'Lift me up',
  escape: 'Pull me away',
  party: 'Make it a party',
  sleep: 'Send me off',
  no_preference: 'Open to anything',
  english: 'English',
  hindi: 'Hindi',
  marathi: 'Marathi',
  punjabi: 'Punjabi',
  instrumental: 'No words, just music',
  discover_new: 'Surprise me',
  old_favorites: 'Songs that feel like home',
  mix_both: 'A bit of both',
};

function copyFor(rawValue) { return OPTION_COPY[rawValue] || ''; }

const MOODS = {
  focused:     { label: 'Focused',     desc: 'Sharp, clear, and ready to move forward.', shape: 'long' },
  energized:   { label: 'Energized',   desc: 'Charged up, alive, and full of momentum.', shape: 'rays' },
  calm:        { label: 'Calm',        desc: 'Grounded, still, and at ease.', shape: 'still' },
  melancholic: { label: 'Melancholic', desc: 'Reflective, tender, and beautifully sad.', shape: 'rain' },
  anxious:     { label: 'Anxious',     desc: 'Restless energy that needs to breathe.', shape: 'tight' },
  celebratory: { label: 'Celebratory', desc: 'Joyful, bright, and ready to share.', shape: 'burst' },
};

function moodMeta(label) {
  return MOODS[label?.toLowerCase()] ||
    { label: label || 'Curated', desc: 'A sound that resonates with you.', shape: 'still' };
}

const HarmonicShared = { getEnergy, waveformPath, humanize, copyFor, moodMeta, MOODS };
export default HarmonicShared;
