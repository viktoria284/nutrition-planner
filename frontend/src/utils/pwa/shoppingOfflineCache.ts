import type { ShoppingListItem } from "../../types/shopping";

const SHOPPING_CACHE_KEY = "shopping_offline_snapshots_v1";

type ShoppingSnapshot = {
  planId: string;
  savedAt: string;
  items: ShoppingListItem[];
};

type ShoppingSnapshotMap = Record<string, ShoppingSnapshot>;

function readSnapshotMap(): ShoppingSnapshotMap {
  try {
    const raw = localStorage.getItem(SHOPPING_CACHE_KEY);
    if (!raw) return {};

    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};

    const entries = Object.entries(parsed as Record<string, unknown>);
    const result: ShoppingSnapshotMap = {};

    for (const [key, value] of entries) {
      if (!value || typeof value !== "object") continue;
      const candidate = value as Partial<ShoppingSnapshot>;

      if (typeof candidate.planId !== "string") continue;
      if (typeof candidate.savedAt !== "string") continue;
      if (!Array.isArray(candidate.items)) continue;

      result[key] = {
        planId: candidate.planId,
        savedAt: candidate.savedAt,
        items: candidate.items as ShoppingListItem[],
      };
    }

    return result;
  } catch {
    return {};
  }
}

function writeSnapshotMap(snapshotMap: ShoppingSnapshotMap): void {
  localStorage.setItem(SHOPPING_CACHE_KEY, JSON.stringify(snapshotMap));
}

export function getOfflineShoppingSnapshot(planId: string): ShoppingSnapshot | null {
  const snapshotMap = readSnapshotMap();
  return snapshotMap[planId] ?? null;
}

export function saveOfflineShoppingSnapshot(planId: string, items: ShoppingListItem[]): ShoppingSnapshot | null {
  try {
    const snapshotMap = readSnapshotMap();
    const savedAt = new Date().toISOString();

    const snapshot: ShoppingSnapshot = {
      planId,
      savedAt,
      items,
    };

    snapshotMap[planId] = snapshot;
    writeSnapshotMap(snapshotMap);

    return snapshot;
  } catch {
    return null;
  }
}
