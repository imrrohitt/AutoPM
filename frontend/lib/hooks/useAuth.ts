"use client";

import { useCallback, useEffect, useState } from "react";
import { authApi } from "@/lib/api";
import { clearTokens, getAccessToken, setTokens } from "@/lib/auth";
import type { UserProfile } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

export function useAuth() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const { data } = await authApi.me();
      setUser(data);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = async (email: string, password: string) => {
    const { data } = await authApi.login({ email, password });
    setTokens(data.access_token, data.refresh_token);
    await fetchMe();
    return data;
  };

  const register = async (payload: {
    company_name: string;
    email: string;
    full_name: string;
    password: string;
  }) => {
    const { data } = await authApi.register(payload);
    setTokens(data.access_token, data.refresh_token);
    await fetchMe();
    return data;
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    clearTokens();
    setUser(null);
  };

  return {
    user,
    loading,
    login,
    register,
    logout,
    refresh: fetchMe,
    errorMessage: getErrorMessage,
  };
}
