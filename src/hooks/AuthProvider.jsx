import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { tokenStore } from "../api/client";
import { authApi } from "../api/auth";

import { AuthContext } from "./authContext";

function readUser() {
  try {
    const user = JSON.parse(localStorage.getItem("tellbook_user"));
    return user && typeof user.id === "number" && tokenStore.getAccess() ? user : null;
  } catch {
    tokenStore.clear();
    return null;
  }
}

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(readUser);

  useEffect(() => {
    if (user) localStorage.setItem("tellbook_user", JSON.stringify(user));
    else localStorage.removeItem("tellbook_user");
  }, [user]);

  useEffect(() => {
    const syncSession = (event) => {
      if (event.key === null || event.key?.startsWith("tellbook_")) {
        queryClient.clear();
        setUser(readUser());
      }
    };
    window.addEventListener("storage", syncSession);
    return () => window.removeEventListener("storage", syncSession);
  }, [queryClient]);

  const login = (userData) => {
    queryClient.clear();
    setUser(userData);
  };
  const logout = () => {
    authApi.logout();
    queryClient.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: Boolean(user && tokenStore.getAccess()), login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
