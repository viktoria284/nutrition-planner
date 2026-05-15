import type { ShoppingListRead } from "../../types/shopping";

const SHOPPING_CACHE_KEY = "shopping_offline_snapshots_v1";

export type ShoppingSnapshot = {
  shoppingListId: string;
  savedAt: string;
  payload: ShoppingListRead;
  pendingCheckedByItemId: Record<string, boolean>;
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

      if (typeof candidate.shoppingListId !== "string") continue;
      if (typeof candidate.savedAt !== "string") continue;
      if (!candidate.payload || typeof candidate.payload !== "object") continue;

      result[key] = {
        shoppingListId: candidate.shoppingListId,
        savedAt: candidate.savedAt,
        payload: candidate.payload as ShoppingListRead,
        pendingCheckedByItemId:
          candidate.pendingCheckedByItemId && typeof candidate.pendingCheckedByItemId === "object"
            ? (candidate.pendingCheckedByItemId as Record<string, boolean>)
            : {},
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

export function getOfflineShoppingSnapshot(shoppingListId: string): ShoppingSnapshot | null {
  const snapshotMap = readSnapshotMap();
  return snapshotMap[shoppingListId] ?? null;
}

export function saveOfflineShoppingSnapshot(
  shoppingListId: string,
  payload: ShoppingListRead,
  pendingCheckedByItemId?: Record<string, boolean>,
): ShoppingSnapshot | null {
  try {
    const snapshotMap = readSnapshotMap();
    const savedAt = new Date().toISOString();

    const snapshot: ShoppingSnapshot = {
      shoppingListId,
      savedAt,
      payload,
      pendingCheckedByItemId: pendingCheckedByItemId ?? snapshotMap[shoppingListId]?.pendingCheckedByItemId ?? {},
    };

    snapshotMap[shoppingListId] = snapshot;
    writeSnapshotMap(snapshotMap);

    return snapshot;
  } catch {
    return null;
  }
}

export function saveOfflineCheckedOverride(
  shoppingListId: string,
  itemId: number,
  checked: boolean,
  payload: ShoppingListRead,
): ShoppingSnapshot | null {
  const existing = getOfflineShoppingSnapshot(shoppingListId);
  const pendingCheckedByItemId = {
    ...(existing?.pendingCheckedByItemId ?? {}),
    [String(itemId)]: checked,
  };
  return saveOfflineShoppingSnapshot(shoppingListId, payload, pendingCheckedByItemId);
}
