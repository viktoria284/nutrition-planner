import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/http";
import { getProfiles, type Profile } from "../api/profiles";
import { useAuth } from "../auth/useAuth";

const ACTIVE_PROFILE_KEY = "activeProfileId";

type ProfilesState = {
  profiles: Profile[];
  activeProfileId: number | null;
  activeProfile: Profile | null;
  loading: boolean;
  error: string | null;
  refreshProfiles: () => Promise<void>;
  setActiveProfileId: (id: number) => void;
};

const ProfilesContext = createContext<ProfilesState | null>(null);

function getStoredActiveProfileId(): number | null {
  const raw = localStorage.getItem(ACTIVE_PROFILE_KEY);
  if (!raw) return null;

  const parsed = Number(raw);
  if (!Number.isInteger(parsed)) return null;
  return parsed;
}

function selectDefaultProfileId(profiles: Profile[], storedId: number | null): number | null {
  if (!profiles.length) return null;

  if (storedId !== null && profiles.some((p) => p.id === storedId)) {
    return storedId;
  }

  const defaultProfile = profiles.find((p) => p.name === "Мой профиль") ?? profiles[0];
  return defaultProfile.id;
}

export function ProfilesProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();

  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfileId, setActiveProfileIdState] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshProfiles = useCallback(async () => {
    if (!token) {
      setProfiles([]);
      setActiveProfileIdState(null);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const items = await getProfiles();
      setProfiles(items);

      const selectedId = selectDefaultProfileId(items, getStoredActiveProfileId());
      setActiveProfileIdState(selectedId);

      if (selectedId === null) localStorage.removeItem(ACTIVE_PROFILE_KEY);
      else localStorage.setItem(ACTIVE_PROFILE_KEY, String(selectedId));
    } catch (err) {
      setProfiles([]);
      setActiveProfileIdState(null);

      if (err instanceof ApiError && err.status === 401) {
        setError("Требуется повторный вход.");
      } else {
        setError(err instanceof Error ? err.message : "Не удалось загрузить профили.");
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void refreshProfiles();
  }, [refreshProfiles]);

  const setActiveProfileId = useCallback((id: number) => {
    setActiveProfileIdState((prev) => {
      if (!profiles.some((p) => p.id === id)) return prev;
      localStorage.setItem(ACTIVE_PROFILE_KEY, String(id));
      return id;
    });
  }, [profiles]);

  const activeProfile = useMemo(
    () => profiles.find((p) => p.id === activeProfileId) ?? null,
    [profiles, activeProfileId],
  );

  const value = useMemo<ProfilesState>(
    () => ({
      profiles,
      activeProfileId,
      activeProfile,
      loading,
      error,
      refreshProfiles,
      setActiveProfileId,
    }),
    [profiles, activeProfileId, activeProfile, loading, error, refreshProfiles, setActiveProfileId],
  );

  return <ProfilesContext.Provider value={value}>{children}</ProfilesContext.Provider>;
}

export function useProfiles() {
  const ctx = useContext(ProfilesContext);
  if (!ctx) throw new Error("useProfiles must be used within ProfilesProvider");
  return ctx;
}
