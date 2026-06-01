import { createContext, useContext, useMemo, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => ({
    token: window.localStorage.getItem("telecom360_token"),
    role: window.localStorage.getItem("telecom360_role")
  }));

  const value = useMemo(
    () => ({
      session,
      setSession(nextSession) {
        if (nextSession?.token) {
          window.localStorage.setItem("telecom360_token", nextSession.token);
          window.localStorage.setItem("telecom360_role", nextSession.role);
        } else {
          window.localStorage.removeItem("telecom360_token");
          window.localStorage.removeItem("telecom360_role");
        }
        setSession(nextSession ?? { token: null, role: null });
      }
    }),
    [session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

