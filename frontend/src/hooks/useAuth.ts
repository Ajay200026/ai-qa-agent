"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  getFirebaseAuth,
  firebaseLogin,
  firebaseLogout,
  firebaseRegister,
  getFirebaseIdToken,
  onAuthStateChanged,
  subscribeIdTokenRefresh,
} from "@/lib/firebase";
import type { User } from "@/lib/types";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const syncBackendUser = useCallback(async () => {
    const token = await getFirebaseIdToken();
    if (!token) {
      setUser(null);
      return;
    }
    localStorage.setItem("token", token);
    const me = await api.getMe();
    setUser(me);
  }, []);

  useEffect(() => {
    const unsubscribeAuth = onAuthStateChanged(getFirebaseAuth(), async (firebaseUser) => {
      if (!firebaseUser) {
        localStorage.removeItem("token");
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        await syncBackendUser();
      } catch (err) {
        console.error("Backend session sync failed:", err);
        localStorage.removeItem("token");
        setUser(null);
      } finally {
        setLoading(false);
      }
    });

    const unsubscribeToken = subscribeIdTokenRefresh((token) => {
      if (token) {
        localStorage.setItem("token", token);
      }
    });

    return () => {
      unsubscribeAuth();
      unsubscribeToken();
    };
  }, [syncBackendUser]);

  const login = async (email: string, password: string) => {
    try {
      await firebaseLogin(email, password);
      await syncBackendUser();
      router.push("/dashboard");
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      if (code === "auth/invalid-credential" || code === "auth/wrong-password") {
        throw new Error("Invalid email or password");
      }
      if (code === "auth/user-not-found") {
        throw new Error("No account found with this email");
      }
      throw err;
    }
  };

  const register = async (email: string, password: string) => {
    try {
      await firebaseRegister(email, password);
      await syncBackendUser();
      router.push("/dashboard");
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      if (code === "auth/email-already-in-use") {
        throw new Error("An account with this email already exists");
      }
      if (code === "auth/weak-password") {
        throw new Error("Password must be at least 6 characters");
      }
      if (code === "auth/invalid-email") {
        throw new Error("Invalid email address");
      }
      throw err;
    }
  };

  const logout = async () => {
    await firebaseLogout();
    localStorage.removeItem("token");
    setUser(null);
    router.push("/login");
  };

  return { user, loading, login, register, logout, isAuthenticated: !!user };
}
