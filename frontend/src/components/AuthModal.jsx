import React, { useState, useEffect } from 'react';
import './AuthModal.css';
import { useAuth } from '../context/AuthContext';
import * as API from '../api';

function HarmonicMark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="13.2" fill="var(--paper-2)" stroke="var(--ink)" strokeWidth="0.7" opacity="0.85" />
      <path d="M5 18 Q9 13, 12 17 T18 16 T26 14" stroke="var(--accent)" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M5 21 Q10 17, 14 20 T22 19" stroke="var(--ink-soft)" strokeWidth="0.9" fill="none" strokeLinecap="round" opacity="0.55" />
      <circle cx="22" cy="11" r="1.6" fill="var(--accent)" />
    </svg>
  );
}

export default function AuthModal() {
  const { isAuthOpen, authMode, authPrompt, closeAuth, onAuthSuccess } = useAuth();
  const [mode, setMode] = useState(authMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setMode(authMode);
    setError('');
  }, [authMode, isAuthOpen]);

  if (!isAuthOpen) return null;

  const isSignUp = mode === 'signup';

  const switchMode = () => {
    setMode(m => m === 'signin' ? 'signup' : 'signin');
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      let user;
      if (isSignUp) {
        user = await API.registerUser({ email, password, firstName, lastName });
      } else {
        user = await API.loginUser({ email, password });
      }
      onAuthSuccess(user);
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="og-auth-overlay" onClick={(e) => { if (e.target === e.currentTarget) closeAuth(); }}>
      <div className="og-auth-card" role="dialog" aria-modal="true">
        <button className="og-auth-close" onClick={closeAuth} aria-label="Close">×</button>

        <div className="og-auth-mark">
          <HarmonicMark size={32} />
        </div>

        <h2 className="og-auth-title">
          {isSignUp ? <>join the <em>field.</em></> : <>welcome <em>back.</em></>}
        </h2>
        <p className="og-auth-sub">
          {isSignUp ? 'create an account to unlock 60-track sessions' : 'sign in to continue listening'}
        </p>

        {authPrompt && (
          <div className="og-auth-prompt">{authPrompt}</div>
        )}

        <form className="og-auth-form" onSubmit={handleSubmit} noValidate>
          {isSignUp && (
            <div className="og-auth-row">
              <div className="og-auth-field">
                <label className="og-auth-label">first name</label>
                <input
                  className="og-auth-input"
                  type="text"
                  placeholder="Ada"
                  value={firstName}
                  onChange={e => setFirstName(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="og-auth-field">
                <label className="og-auth-label">last name</label>
                <input
                  className="og-auth-input"
                  type="text"
                  placeholder="Lovelace"
                  value={lastName}
                  onChange={e => setLastName(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className="og-auth-field">
            <label className="og-auth-label">email</label>
            <input
              className="og-auth-input"
              type="email"
              placeholder="you@somewhere.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus={!isSignUp}
            />
          </div>

          <div className="og-auth-field">
            <label className="og-auth-label">password</label>
            <input
              className="og-auth-input"
              type="password"
              placeholder={isSignUp ? 'at least 6 characters' : '········'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className="og-auth-error">{error}</p>}

          <button
            type="submit"
            className="og-btn og-btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            disabled={loading}
          >
            {loading ? 'one moment…' : isSignUp ? 'create account ▸' : 'sign in ▸'}
          </button>
        </form>

        <div className="og-auth-divider"><span>or</span></div>

        <div className="og-auth-switch">
          {isSignUp ? 'already have an account? ' : 'new here? '}
          <button onClick={switchMode}>
            {isSignUp ? 'sign in' : 'create account'}
          </button>
        </div>
      </div>
    </div>
  );
}
