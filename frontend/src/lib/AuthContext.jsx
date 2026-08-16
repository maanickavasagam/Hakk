import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, clearToken, getToken, setToken } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch {
        clearToken();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    const onUnauth = () => setUser(null);
    window.addEventListener('hakk:unauthorised', onUnauth);
    return () => {
      cancelled = true;
      window.removeEventListener('hakk:unauthorised', onUnauth);
    };
  }, []);

  const signIn = useCallback((token, nextUser) => {
    setToken(token);
    setUser(nextUser);
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, setUser, loading, signIn, signOut }),
    [user, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
};
