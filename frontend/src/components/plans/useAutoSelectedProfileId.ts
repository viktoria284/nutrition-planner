import { useEffect } from "react";
import type { Profile } from "../../api/profiles";

type UseAutoSelectedProfileIdParams = {
  profiles: Profile[];
  activeProfileId: number | null;
  currentProfileId: string;
  setProfileId: (nextProfileId: string) => void;
};

function resolveAutoSelectedProfileId(
  profiles: Profile[],
  activeProfileId: number | null,
  currentProfileId: string,
): string {
  if (profiles.length === 0) return "";

  const currentId = Number(currentProfileId);
  if (Number.isInteger(currentId) && profiles.some((profile) => profile.id === currentId)) {
    return String(currentId);
  }

  if (activeProfileId !== null && profiles.some((profile) => profile.id === activeProfileId)) {
    return String(activeProfileId);
  }

  return String(profiles[0].id);
}

export function useAutoSelectedProfileId({
  profiles,
  activeProfileId,
  currentProfileId,
  setProfileId,
}: UseAutoSelectedProfileIdParams) {
  useEffect(() => {
    const nextProfileId = resolveAutoSelectedProfileId(
      profiles,
      activeProfileId,
      currentProfileId,
    );
    if (nextProfileId === currentProfileId) return;
    setProfileId(nextProfileId);
  }, [activeProfileId, currentProfileId, profiles, setProfileId]);
}
