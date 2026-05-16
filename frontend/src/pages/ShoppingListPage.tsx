import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { ApiError } from "../api/http";
import { getPlan } from "../api/plans";
import {
  createManualShoppingItem,
  deleteShoppingList,
  deleteShoppingListItem,
  getShoppingList,
  patchShoppingItem,
  rebuildShoppingList,
} from "../api/shopping";
import { Alert } from "../components/Alert";
import { AddManualShoppingItemModal } from "../components/plans/AddManualShoppingItemModal";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { FOOD_CATEGORIES, FOOD_CATEGORY_LABELS, type FoodCategory } from "../types/foodCategory";
import type { PlanRead } from "../types/plan";
import type { ShoppingListItem, ShoppingListRead, ShoppingManualItemCreatePayload } from "../types/shopping";
import {
  getOfflineShoppingSnapshot,
  saveOfflineCheckedOverride,
  saveOfflineShoppingSnapshot,
} from "../utils/pwa/shoppingOfflineCache";
import "./PlansPage.css";

const HIDE_CHECKED_STORAGE_KEY = "nutrition:shopping-list:hide-checked";

function collapsedCategoriesStorageKey(shoppingListId: number): string {
  return `nutrition:shopping-list:${shoppingListId}:collapsed-categories`;
}

function readBooleanStorage(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeBooleanStorage(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    // ignore storage write errors
  }
}

function readCollapsedCategories(shoppingListId: number): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(collapsedCategoriesStorageKey(shoppingListId));
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as Record<string, boolean>;
  } catch {
    return {};
  }
}

function writeCollapsedCategories(shoppingListId: number, value: Record<string, boolean>): void {
  try {
    localStorage.setItem(collapsedCategoriesStorageKey(shoppingListId), JSON.stringify(value));
  } catch {
    // ignore storage write errors
  }
}

function resolveError(err: unknown, notFoundMessage: string): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return notFoundMessage;
    if (err.status === 422) return "Проверьте введённые данные.";
    if (err.status === 409) return "Конфликт сохранения. Обновите данные и повторите попытку.";
  }
  return err instanceof Error ? err.message : "Не удалось выполнить операцию.";
}

function normalizePositiveDecimal(raw: string): { value: string | null; error: string | null } {
  const normalized = raw.trim().replace(",", ".");
  if (!normalized) return { value: null, error: "Укажите количество." };
  if (!/^\d+(\.\d+)?$/.test(normalized)) {
    return { value: null, error: "Количество должно быть положительным числом." };
  }
  if (Number(normalized) <= 0) {
    return { value: null, error: "Количество должно быть больше 0." };
  }
  return { value: normalized, error: null };
}

function formatDecimalRu(value: number, maximumFractionDigits: number): string {
  return value.toLocaleString("ru-RU", {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  });
}

export function formatShoppingQuantity(amount: string | number | null | undefined, unit?: string | null): string {
  if (amount === null || amount === undefined || amount === "") return "Количество не указано";

  const normalizedUnit = (unit ?? "g").trim().toLowerCase();
  const numeric = Number(String(amount).replace(",", "."));
  if (!Number.isFinite(numeric)) return "Количество не указано";

  if (normalizedUnit === "g" || normalizedUnit === "г") {
    if (numeric >= 1000) {
      return `${formatDecimalRu(numeric / 1000, 2)} кг`;
    }
    return `${Math.round(numeric)} г`;
  }

  const displayUnit = normalizedUnit === "kg" ? "кг" : unit?.trim() || normalizedUnit;
  return `${formatDecimalRu(numeric, 2)} ${displayUnit}`;
}

function displayAmount(item: ShoppingListItem): string {
  return formatShoppingQuantity(item.effective_grams ?? item.planned_grams, item.unit);
}

function formatSavedAt(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isNetworkError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 0;
}

function applyPendingCheckedOverrides(
  list: ShoppingListRead,
  overrides: Record<string, boolean>,
): { list: ShoppingListRead; appliedCount: number } {
  if (Object.keys(overrides).length === 0) return { list, appliedCount: 0 };

  let appliedCount = 0;
  const items = list.items.map((item) => {
    const nextChecked = overrides[String(item.id)];
    if (typeof nextChecked !== "boolean" || item.checked === nextChecked) {
      return item;
    }
    appliedCount += 1;
    return { ...item, checked: nextChecked };
  });

  if (appliedCount === 0) return { list, appliedCount: 0 };
  return { list: { ...list, items }, appliedCount };
}

export function ShoppingListPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isOnline } = useOnlineStatus();
  const previousOnlineRef = useRef<boolean>(isOnline);

  const [shoppingList, setShoppingList] = useState<ShoppingListRead | null>(null);
  const [sourcePlan, setSourcePlan] = useState<PlanRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [patchingItemIds, setPatchingItemIds] = useState<Set<number>>(new Set());
  const [draftAdjustedByItemId, setDraftAdjustedByItemId] = useState<Record<number, string>>({});
  const [rowErrorsByItemId, setRowErrorsByItemId] = useState<Record<number, string>>({});

  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [creatingManual, setCreatingManual] = useState(false);
  const [createManualError, setCreateManualError] = useState<string | null>(null);

  const [itemToDelete, setItemToDelete] = useState<ShoppingListItem | null>(null);
  const [deletingItem, setDeletingItem] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [deleteListModalOpen, setDeleteListModalOpen] = useState(false);
  const [deletingList, setDeletingList] = useState(false);
  const [deleteListError, setDeleteListError] = useState<string | null>(null);

  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildError, setRebuildError] = useState<string | null>(null);
  const [loadedFromOfflineCache, setLoadedFromOfflineCache] = useState(false);
  const [offlineSavedAt, setOfflineSavedAt] = useState<string | null>(null);
  const [offlineMissingMessage, setOfflineMissingMessage] = useState<string | null>(null);
  const [offlinePendingChanges, setOfflinePendingChanges] = useState(false);
  const [offlineSyncHint, setOfflineSyncHint] = useState<string | null>(null);
  const [hideCheckedItems, setHideCheckedItems] = useState<boolean>(() => readBooleanStorage(HIDE_CHECKED_STORAGE_KEY));
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  const shoppingListId = useMemo(() => {
    const parsed = Number(id);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [id]);

  const loadShoppingList = useCallback(
    async (options?: { background?: boolean }) => {
      if (!shoppingListId) {
        setError("Некорректный идентификатор списка покупок.");
        setLoading(false);
        return;
      }

      if (options?.background) setRefreshing(true);
      else setLoading(true);

      setError(null);
      setOfflineMissingMessage(null);
      try {
        const loaded = await getShoppingList(shoppingListId);
        const cacheKey = String(shoppingListId);
        const snapshot = getOfflineShoppingSnapshot(cacheKey);
        const withPending = applyPendingCheckedOverrides(loaded, snapshot?.pendingCheckedByItemId ?? {});

        setShoppingList(withPending.list);
        setLoadedFromOfflineCache(false);
        setOfflinePendingChanges(withPending.appliedCount > 0);
        if (withPending.appliedCount > 0) {
          setOfflineSyncHint("Подключение восстановлено. Обновите список, чтобы синхронизировать данные.");
        } else if (isOnline) {
          setOfflineSyncHint(null);
        }

        const saved = saveOfflineShoppingSnapshot(cacheKey, withPending.list, snapshot?.pendingCheckedByItemId ?? {});
        setOfflineSavedAt(saved?.savedAt ?? null);

        const planId = loaded.sources[0]?.plan_id;
        if (planId) {
          try {
            const plan = await getPlan(planId);
            setSourcePlan(plan);
          } catch {
            setSourcePlan(null);
          }
        } else {
          setSourcePlan(null);
        }
      } catch (err) {
        if (isNetworkError(err) && shoppingListId) {
          const snapshot = getOfflineShoppingSnapshot(String(shoppingListId));
          if (snapshot) {
            const withPending = applyPendingCheckedOverrides(snapshot.payload, snapshot.pendingCheckedByItemId);
            setShoppingList(withPending.list);
            setSourcePlan(null);
            setLoadedFromOfflineCache(true);
            setOfflineSavedAt(snapshot.savedAt);
            setOfflinePendingChanges(Object.keys(snapshot.pendingCheckedByItemId).length > 0);
            setOfflineSyncHint(
              Object.keys(snapshot.pendingCheckedByItemId).length > 0
                ? "Изменения сохранены на устройстве и будут применены после подключения."
                : null,
            );
            setError(null);
          } else {
            setShoppingList(null);
            setSourcePlan(null);
            setError("Не удалось загрузить список без подключения к интернету.");
            setOfflineMissingMessage(
              "Список пока не сохранён для офлайн-доступа. Откройте его один раз при подключении к интернету.",
            );
          }
        } else {
          setShoppingList(null);
          setSourcePlan(null);
          setError(resolveError(err, "Список покупок не найден."));
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [isOnline, shoppingListId],
  );

  useEffect(() => {
    void loadShoppingList();
  }, [loadShoppingList]);

  useEffect(() => {
    if (!shoppingList) {
      setDraftAdjustedByItemId({});
      return;
    }

    const nextDrafts: Record<number, string> = {};
    for (const item of shoppingList.items) {
      if (item.item_type !== "computed") continue;
      nextDrafts[item.id] = item.adjusted_grams ?? item.effective_grams ?? "";
    }
    setDraftAdjustedByItemId(nextDrafts);
  }, [shoppingList]);

  useEffect(() => {
    const wasOnline = previousOnlineRef.current;
    if (wasOnline === isOnline) return;

    if (!wasOnline && isOnline && offlinePendingChanges) {
      setOfflineSyncHint("Подключение восстановлено. Обновите список, чтобы синхронизировать данные.");
    }

    if (wasOnline && !isOnline) {
      setOfflineSyncHint((prev) => prev ?? "Вы в офлайне. Доступна последняя сохранённая копия списка.");
    }

    previousOnlineRef.current = isOnline;
  }, [isOnline, offlinePendingChanges]);

  useEffect(() => {
    if (!shoppingListId) return;
    setCollapsedCategories(readCollapsedCategories(shoppingListId));
  }, [shoppingListId]);

  useEffect(() => {
    writeBooleanStorage(HIDE_CHECKED_STORAGE_KEY, hideCheckedItems);
  }, [hideCheckedItems]);

  const baseVisibleItems = useMemo(() => shoppingList?.items.filter((item) => !item.excluded) ?? [], [shoppingList]);
  const queryNormalized = searchQuery.trim().toLowerCase();

  const searchFilteredVisibleItems = useMemo(() => {
    if (!queryNormalized) return baseVisibleItems;
    return baseVisibleItems.filter((item) => item.name_snapshot.toLowerCase().includes(queryNormalized));
  }, [baseVisibleItems, queryNormalized]);

  const visibleItems = useMemo(() => {
    if (!hideCheckedItems) return searchFilteredVisibleItems;
    return searchFilteredVisibleItems.filter((item) => !item.checked);
  }, [hideCheckedItems, searchFilteredVisibleItems]);

  const hiddenByCheckedCount = useMemo(() => {
    if (!hideCheckedItems) return 0;
    return searchFilteredVisibleItems.filter((item) => item.checked).length;
  }, [hideCheckedItems, searchFilteredVisibleItems]);

  const hiddenItems = useMemo(() => {
    const excluded = shoppingList?.items.filter((item) => item.excluded) ?? [];
    if (!queryNormalized) return excluded;
    return excluded.filter((item) => item.name_snapshot.toLowerCase().includes(queryNormalized));
  }, [shoppingList, queryNormalized]);

  const groupedVisibleItems = useMemo(() => {
    const groups: Record<FoodCategory, ShoppingListItem[]> = {
      vegetables: [],
      fruits: [],
      dairy: [],
      eggs: [],
      meat_fish: [],
      grains_bakery: [],
      pantry_spices: [],
      nuts_oils: [],
      drinks: [],
      sweets: [],
      frozen: [],
      other: [],
    };

    for (const item of visibleItems) {
      groups[item.category].push(item);
    }

    for (const category of FOOD_CATEGORIES) {
      groups[category].sort((a, b) => {
        if (a.checked !== b.checked) return a.checked ? 1 : -1;
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.name_snapshot.localeCompare(b.name_snapshot, "ru");
      });
    }

    return groups;
  }, [visibleItems]);

  useEffect(() => {
    if (!shoppingListId) return;
    writeCollapsedCategories(shoppingListId, collapsedCategories);
  }, [collapsedCategories, shoppingListId]);

  const hasAnyVisibleCategoryItems = useMemo(
    () => FOOD_CATEGORIES.some((category) => groupedVisibleItems[category].length > 0),
    [groupedVisibleItems],
  );

  const hasAnyDisplayItems = hasAnyVisibleCategoryItems || hiddenItems.length > 0;

  const exportTxt = () => {
    if (!shoppingList) return;

    const lines: string[] = [];
    lines.push(`Список покупок: ${shoppingList.title || `#${shoppingList.id}`}`);
    lines.push(`Сохранено: ${formatSavedAt(offlineSavedAt)}`);
    lines.push("");

    for (const category of FOOD_CATEGORIES) {
      const categoryItems = groupedVisibleItems[category];
      if (categoryItems.length === 0) continue;
      lines.push(FOOD_CATEGORY_LABELS[category]);
      for (const item of categoryItems) {
        const checkedPrefix = item.checked ? "✓ " : "";
        lines.push(`- ${checkedPrefix}${item.name_snapshot} — ${displayAmount(item)}`);
      }
      lines.push("");
    }

    if (hiddenItems.length > 0) {
      lines.push("Скрытые позиции");
      for (const item of hiddenItems) {
        lines.push(`- ${item.name_snapshot} — ${displayAmount(item)}`);
      }
      lines.push("");
    }

    const content = `${lines.join("\n").trim()}\n`;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const datePart = shoppingList.created_at.slice(0, 10);
    link.href = url;
    link.download = `shopping-list-${shoppingList.id}-${datePart}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const withItemPatch = async (itemId: number, action: () => Promise<void>) => {
    if (!shoppingList) return;

    setPatchingItemIds((prev) => new Set(prev).add(itemId));
    setRowErrorsByItemId((prev) => {
      const next = { ...prev };
      delete next[itemId];
      return next;
    });

    try {
      await action();
      await loadShoppingList({ background: true });
    } catch (err) {
      setRowErrorsByItemId((prev) => ({
        ...prev,
        [itemId]: resolveError(err, "Позиция не найдена."),
      }));
    } finally {
      setPatchingItemIds((prev) => {
        const next = new Set(prev);
        next.delete(itemId);
        return next;
      });
    }
  };

  const handleToggleChecked = async (item: ShoppingListItem) => {
    if (!shoppingList) return;

    if (!isOnline) {
      const nextChecked = !item.checked;
      const nextList: ShoppingListRead = {
        ...shoppingList,
        items: shoppingList.items.map((entry) => (entry.id === item.id ? { ...entry, checked: nextChecked } : entry)),
      };
      setShoppingList(nextList);

      const saved = saveOfflineCheckedOverride(String(shoppingList.id), item.id, nextChecked, nextList);
      setOfflineSavedAt(saved?.savedAt ?? offlineSavedAt);
      setLoadedFromOfflineCache(true);
      setOfflinePendingChanges(true);
      setOfflineSyncHint("Изменения сохранены на устройстве и будут применены после подключения.");
      setRowErrorsByItemId((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      return;
    }

    await withItemPatch(item.id, async () => {
      await patchShoppingItem(shoppingList.id, item.id, { checked: !item.checked });
    });
  };

  const handleSaveAdjusted = async (item: ShoppingListItem) => {
    if (!shoppingList) return;
    const draft = draftAdjustedByItemId[item.id] ?? "";
    const normalized = normalizePositiveDecimal(draft);
    if (!normalized.value) {
      setRowErrorsByItemId((prev) => ({
        ...prev,
        [item.id]: normalized.error ?? "Проверьте значение количества.",
      }));
      return;
    }

    await withItemPatch(item.id, async () => {
      await patchShoppingItem(shoppingList.id, item.id, { adjusted_grams: normalized.value });
    });
  };

  const handleResetAdjusted = async (item: ShoppingListItem) => {
    if (!shoppingList) return;
    await withItemPatch(item.id, async () => {
      await patchShoppingItem(shoppingList.id, item.id, { adjusted_grams: null });
    });
  };

  const handleDeleteItem = async () => {
    if (!shoppingList || !itemToDelete) return;

    setDeletingItem(true);
    setDeleteError(null);
    try {
      await deleteShoppingListItem(shoppingList.id, itemToDelete.id);
      setItemToDelete(null);
      await loadShoppingList({ background: true });
    } catch (err) {
      setDeleteError(resolveError(err, "Позиция не найдена."));
    } finally {
      setDeletingItem(false);
    }
  };

  const handleDeleteList = async () => {
    if (!shoppingList) return;

    setDeletingList(true);
    setDeleteListError(null);
    try {
      await deleteShoppingList(shoppingList.id);
      navigate("/shopping-lists");
    } catch (err) {
      setDeleteListError(resolveError(err, "Список покупок не найден."));
    } finally {
      setDeletingList(false);
    }
  };

  const handleCreateManual = async (payload: ShoppingManualItemCreatePayload) => {
    if (!shoppingList) return;

    setCreatingManual(true);
    setCreateManualError(null);
    try {
      await createManualShoppingItem(shoppingList.id, payload);
      setManualModalOpen(false);
      await loadShoppingList({ background: true });
    } catch (err) {
      setCreateManualError(resolveError(err, "Не удалось добавить ручную позицию."));
    } finally {
      setCreatingManual(false);
    }
  };

  const handleRebuild = async () => {
    if (!shoppingList) return;

    setRebuilding(true);
    setRebuildError(null);
    try {
      const rebuilt = await rebuildShoppingList(shoppingList.id);
      setShoppingList(rebuilt);
      const saved = saveOfflineShoppingSnapshot(String(rebuilt.id), rebuilt, {});
      setOfflineSavedAt(saved?.savedAt ?? offlineSavedAt);
      setLoadedFromOfflineCache(false);
      setOfflinePendingChanges(false);
      setOfflineSyncHint(null);
      await loadShoppingList({ background: true });
    } catch (err) {
      setRebuildError(resolveError(err, "Не удалось пересобрать список."));
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <section className="plans-page shopping-list--compact">
      <div className="plans-shell plans-shell-wide">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Список покупок</h1>
            <p className="plans-subtitle">
              {sourcePlan
                ? `Источник: план «${sourcePlan.title ?? sourcePlan.start_date}».`
                : shoppingList?.sources[0]
                  ? "Источник: план."
                : "Источник не указан."}
            </p>
          </div>
          <div className="plans-head-actions shopping-header-actions-desktop">
            <Link to="/shopping-lists" className="btn btn-secondary">
              К спискам покупок
            </Link>
            {sourcePlan && (
              <Link to={`/plans/${sourcePlan.id}`} className="btn btn-secondary">
                К плану
              </Link>
            )}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void loadShoppingList({ background: true })}
              disabled={loading || refreshing}
            >
              {refreshing ? "Обновляем..." : "Обновить"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setManualModalOpen(true)}
              disabled={!shoppingList || !isOnline}
            >
              Добавить вручную
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setDeleteListError(null);
                setDeleteListModalOpen(true);
              }}
              disabled={!shoppingList || !isOnline}
            >
              Удалить список
            </button>
          </div>

          <div className="shopping-mobile-toolbar no-print" aria-label="Быстрые действия списка покупок">
            <Link to="/shopping-lists" className="btn btn-secondary shopping-mobile-btn">
              Назад
            </Link>
            {sourcePlan && (
              <Link to={`/plans/${sourcePlan.id}`} className="btn btn-secondary shopping-mobile-btn">
                К плану
              </Link>
            )}
            <button
              type="button"
              className="icon-button icon-button--secondary shopping-mobile-refresh"
              onClick={() => void loadShoppingList({ background: true })}
              disabled={loading || refreshing}
              aria-label={refreshing ? "Обновляем список" : "Обновить список"}
            >
              <RefreshCw aria-hidden="true" size={16} />
            </button>
            <button
              type="button"
              className="btn btn-primary shopping-mobile-add"
              onClick={() => setManualModalOpen(true)}
              disabled={!shoppingList || !isOnline}
              aria-label="Добавить вручную"
            >
              <span className="shopping-mobile-add-label-full">+ Добавить</span>
              <span className="shopping-mobile-add-label-short">+</span>
            </button>
            <details className="shopping-mobile-more">
              <summary className="icon-button icon-button--secondary shopping-mobile-more-trigger">Ещё</summary>
              <div className="shopping-mobile-more-panel">
                <button type="button" className="btn btn-secondary shopping-mobile-more-btn" onClick={() => window.print()}>
                  Печать
                </button>
                <button type="button" className="btn btn-secondary shopping-mobile-more-btn" onClick={exportTxt}>
                  Экспорт .txt
                </button>
                <button
                  type="button"
                  className="btn btn-secondary shopping-mobile-more-btn"
                  onClick={() => {
                    setDeleteListError(null);
                    setDeleteListModalOpen(true);
                  }}
                  disabled={!shoppingList || !isOnline}
                >
                  Удалить список
                </button>
              </div>
            </details>
          </div>
        </header>

        {loading && <p className="plans-note">Загрузка списка покупок...</p>}
        {!loading && refreshing && <p className="plans-note">Синхронизируем изменения...</p>}

        {!loading && shoppingList && (
          <div className="plan-shopping-status-row">
            <p className="plan-shopping-network-status" role="status">
              <span className={`plan-shopping-network-dot ${isOnline ? "is-online" : "is-offline"}`} />
              {isOnline ? "Онлайн" : "Офлайн"}
            </p>
            {loadedFromOfflineCache ? (
              <p className="plan-shopping-offline-note">
                Вы открыли сохранённую копию списка. Данные могут быть неактуальны. Сохранено: {formatSavedAt(offlineSavedAt)}.
              </p>
            ) : (
              <p className="plan-shopping-offline-note">
                Список сохранён для офлайн-доступа. Сохранено: {formatSavedAt(offlineSavedAt)}.
              </p>
            )}
          </div>
        )}

        {!loading && shoppingList && offlineSyncHint && (
          <article className="plan-shopping-offline-banner" role="status">
            <p>{offlineSyncHint}</p>
          </article>
        )}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
            {offlineMissingMessage && <p className="plan-shopping-offline-note">{offlineMissingMessage}</p>}
            <button type="button" className="btn btn-secondary" onClick={() => void loadShoppingList()}>
              Повторить
            </button>
          </div>
        )}

        {!loading && !error && shoppingList && shoppingList.is_outdated && (
          <article className="plan-shopping-outdated-banner" role="status">
            <div>
              <p className="plan-shopping-outdated-title">План изменился после создания списка.</p>
              <p className="plan-shopping-outdated-text">
                Пересоберите список, чтобы обновить рассчитанные количества. Ручные позиции сохранятся.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary plan-shopping-rebuild-btn"
              onClick={() => void handleRebuild()}
              disabled={rebuilding || !isOnline}
            >
              <RefreshCw aria-hidden="true" size={18} />
              {rebuilding ? "Пересобираем..." : "Пересобрать список"}
            </button>
          </article>
        )}

        {rebuildError && <Alert text={rebuildError} />}

        {!loading && !error && shoppingList && baseVisibleItems.length === 0 && hiddenItems.length === 0 && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Список пока пуст</p>
            <p className="plans-empty-subtitle">Добавьте ручные позиции или пересоберите список после заполнения плана.</p>
            <button type="button" className="btn btn-primary" onClick={() => setManualModalOpen(true)} disabled={!isOnline}>
              Добавить вручную
            </button>
          </article>
        )}

        {!loading && !error && shoppingList && (baseVisibleItems.length > 0 || hiddenItems.length > 0) && (
          <div className="plan-shopping-grid">
            <section className="plan-shopping-controls-panel" aria-label="Параметры отображения списка">
              <div className="plan-shopping-controls-top">
                <label className="plans-field plan-shopping-search-field" htmlFor="shopping-list-search">
                  <span className="plans-field-label">Поиск</span>
                  <input
                    id="shopping-list-search"
                    className="plans-field-input"
                    type="search"
                    placeholder="Найти продукт в списке"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </label>
                <div className="plan-shopping-controls-actions plan-shopping-controls-actions-desktop no-print">
                  <button type="button" className="btn btn-secondary" onClick={() => window.print()}>
                    Печать
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={exportTxt}>
                    Экспорт .txt
                  </button>
                </div>
              </div>

              <div className="plan-shopping-controls-row">
                <label className="plans-checkbox-row">
                  <input
                    type="checkbox"
                    checked={hideCheckedItems}
                    onChange={(event) => setHideCheckedItems(event.target.checked)}
                  />
                  <span>Скрыть отмеченные</span>
                </label>
                {hideCheckedItems && hiddenByCheckedCount > 0 && (
                  <p className="plan-shopping-controls-note">Скрыто отмеченных: {hiddenByCheckedCount}</p>
                )}
              </div>
            </section>

            {!hasAnyDisplayItems && (
              <article className="plans-empty-card">
                <p className="plans-empty-title">Ничего не найдено</p>
                <p className="plans-empty-subtitle">Попробуйте изменить поиск или отключить фильтр скрытия отмеченных.</p>
              </article>
            )}

            {FOOD_CATEGORIES.map((category) => {
              const categoryItems = groupedVisibleItems[category];
              if (categoryItems.length === 0) return null;
              const isCollapsed = collapsedCategories[category] === true;
              return (
                <section key={category} className="plan-shopping-card" aria-label={FOOD_CATEGORY_LABELS[category]}>
                  <button
                    type="button"
                    className="plan-shopping-section-toggle"
                    onClick={() =>
                      setCollapsedCategories((prev) => ({
                        ...prev,
                        [category]: !isCollapsed,
                      }))
                    }
                    aria-expanded={!isCollapsed}
                  >
                    <span className="plan-shopping-section-title-wrap">
                      <span className="plan-shopping-section-arrow" aria-hidden="true">
                        {isCollapsed ? "▸" : "▾"}
                      </span>
                      <span className="plan-shopping-section-title">{FOOD_CATEGORY_LABELS[category]}</span>
                    </span>
                    <span className="plan-shopping-section-count">{categoryItems.length}</span>
                  </button>

                  {!isCollapsed && (
                    <ul className="plan-shopping-list">
                      {categoryItems.map((item) => {
                      const isSaving = patchingItemIds.has(item.id);
                      const rowError = rowErrorsByItemId[item.id];
                      const isChecked = item.checked;
                      const isManual = item.item_type === "manual";

                      return (
                        <li key={item.id} className={`plan-shopping-item ${isChecked ? "is-checked" : ""}`}>
                          <div className="plan-shopping-item-top">
                            <div className="plan-shopping-main">
                              <div className="plan-shopping-title-row">
                                <p className="plan-shopping-name">{item.name_snapshot}</p>
                                {isManual && <span className="plan-shopping-badge">добавлено вручную</span>}
                              </div>
                              <p className="plan-shopping-meta">Количество: {displayAmount(item)}</p>
                              {!isManual && item.adjusted_grams !== null && (
                                <p className="plan-shopping-meta">изменено вручную</p>
                              )}
                            </div>

                            <label className="plan-shopping-checkbox plan-shopping-checkbox-main">
                              <input
                                aria-label={item.checked ? "Отметить как нужно купить" : "Отметить как уже куплено"}
                                type="checkbox"
                                checked={item.checked}
                                disabled={isSaving}
                                onChange={() => {
                                  void handleToggleChecked(item);
                                }}
                              />
                            </label>
                          </div>

                          <div className="plan-shopping-controls">
                            {isManual ? (
                              <button
                                type="button"
                                className="btn btn-secondary plan-shopping-inline-btn"
                                disabled={isSaving || !isOnline}
                                onClick={() => {
                                  setDeleteError(null);
                                  setItemToDelete(item);
                                }}
                              >
                                Удалить
                              </button>
                            ) : (
                              <div className="plan-shopping-adjust-row">
                                <input
                                  className="plans-field-input plan-shopping-adjust-input"
                                  type="text"
                                  inputMode="decimal"
                                  value={draftAdjustedByItemId[item.id] ?? ""}
                                  disabled={isSaving || !isOnline}
                                  onChange={(event) => {
                                    const next = event.target.value;
                                    setDraftAdjustedByItemId((prev) => ({ ...prev, [item.id]: next }));
                                    setRowErrorsByItemId((prev) => {
                                      const updated = { ...prev };
                                      delete updated[item.id];
                                      return updated;
                                    });
                                  }}
                                />
                                <button
                                  type="button"
                                  className="btn btn-secondary plan-shopping-inline-btn"
                                  disabled={isSaving || !isOnline}
                                  onClick={() => {
                                    void handleSaveAdjusted(item);
                                  }}
                                >
                                  Сохранить
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary plan-shopping-inline-btn"
                                  disabled={isSaving || item.adjusted_grams === null || !isOnline}
                                  onClick={() => {
                                    void handleResetAdjusted(item);
                                  }}
                                >
                                  Сбросить
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary plan-shopping-inline-btn plan-shopping-hide-btn"
                                  disabled={isSaving || !isOnline}
                                  onClick={() => {
                                    setDeleteError(null);
                                    setItemToDelete(item);
                                  }}
                                >
                                  Скрыть
                                </button>
                              </div>
                            )}

                            {rowError && <p className="plan-shopping-row-error">{rowError}</p>}
                          </div>
                        </li>
                      );
                      })}
                    </ul>
                  )}
                </section>
              );
            })}

            {hiddenItems.length > 0 && (
              <section className="plan-shopping-card" aria-label="Скрытые позиции">
                <h2 className="plan-shopping-section-title">Скрытые позиции ({hiddenItems.length})</h2>
                <ul className="plan-shopping-list">
                  {hiddenItems.map((item) => {
                    const isSaving = patchingItemIds.has(item.id);
                    const rowError = rowErrorsByItemId[item.id];
                    return (
                      <li key={item.id} className="plan-shopping-item is-hidden">
                        <div className="plan-shopping-main">
                          <p className="plan-shopping-name">{item.name_snapshot}</p>
                          <p className="plan-shopping-meta">{FOOD_CATEGORY_LABELS[item.category]}</p>
                        </div>
                        <div className="plan-shopping-controls plan-shopping-controls-manual">
                          <button
                            type="button"
                            className="btn btn-secondary plan-shopping-inline-btn"
                            disabled={isSaving || !isOnline}
                            onClick={() => {
                              void withItemPatch(item.id, async () => {
                                await patchShoppingItem(shoppingList.id, item.id, { excluded: false });
                              });
                            }}
                          >
                            Вернуть
                          </button>
                          {rowError && <p className="plan-shopping-row-error">{rowError}</p>}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>

      <AddManualShoppingItemModal
        open={manualModalOpen && shoppingList !== null}
        saving={creatingManual || !isOnline}
        submitError={createManualError}
        onClose={() => {
          if (creatingManual) return;
          setManualModalOpen(false);
        }}
        onSubmit={handleCreateManual}
      />

      <PlanConfirmModal
        open={itemToDelete !== null}
        title={itemToDelete?.item_type === "manual" ? "Удалить ручную позицию" : "Скрыть позицию"}
        message={
          itemToDelete
            ? itemToDelete.item_type === "manual"
              ? `Позиция «${itemToDelete.name_snapshot}» будет удалена.`
              : `Позиция «${itemToDelete.name_snapshot}» будет скрыта из основного списка.`
            : ""
        }
        confirmText={itemToDelete?.item_type === "manual" ? "Удалить" : "Скрыть"}
        loading={deletingItem}
        loadingText={itemToDelete?.item_type === "manual" ? "Удаляем..." : "Скрываем..."}
        errorText={deleteError}
        onClose={() => {
          if (deletingItem) return;
          setItemToDelete(null);
        }}
        onConfirm={() => {
          void handleDeleteItem();
        }}
      />

      <PlanConfirmModal
        open={deleteListModalOpen}
        title="Удалить список покупок?"
        message="Список будет удалён без возможности восстановления."
        confirmText="Удалить"
        loading={deletingList}
        loadingText="Удаляем..."
        errorText={deleteListError}
        onClose={() => {
          if (deletingList) return;
          setDeleteListModalOpen(false);
        }}
        onConfirm={() => {
          void handleDeleteList();
        }}
      />
    </section>
  );
}
