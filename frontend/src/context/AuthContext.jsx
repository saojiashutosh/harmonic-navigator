import React, { createContext, useContext, useEffect, useState } from 'react';
import { fetchMe, logoutUser } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]           = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [authMode, setAuthMode]   = useState('signin'); // 'signin' | 'signup'
  const [authPrompt, setAuthPrompt] = useState(null);

  // Restore session on mount
  useEffect(() => {
    fetchMe()
      .then(u => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setAuthReady(true));
  }, []);

  const openAuth = (mode = 'signin', prompt = null) => {
    setAuthMode(mode);
    setAuthPrompt(prompt);
    setIsAuthOpen(true);
  };

  const closeAuth = () => {
    setIsAuthOpen(false);
    setAuthPrompt(null);
  };

  // Called by AuthModal after a successful login or register
  const onAuthSuccess = (userData) => {
    setUser(userData);
    closeAuth();
  };

  const logout = async () => {
    await logoutUser();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user,
      authReady,
      isAuthOpen,
      authMode,
      authPrompt,
      openAuth,
      closeAuth,
      onAuthSuccess,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
