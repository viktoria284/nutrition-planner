import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  createManualShoppingItem,
  deleteManualShoppingItem,
  getPlanShoppingList,
  patchShoppingItem,
} from "../api/shopping";
import { Alert } from "../components/Alert";
import { AddManualShoppingItemModal } from "../components/plans/AddManualShoppingItemModal";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import { useNetworkStatus } from "../hooks/useNetworkStatus";
import type {
  ShoppingComputedItem,
  ShoppingListItem,
  ShoppingManualItem,
  ShoppingManualItemCreatePayload,
} from "../types/shopping";
import {
  getOfflineShoppingSnapshot,
  saveOfflineShoppingSnapshot,
} from "../utils/pwa/shoppingOfflineCache";
import { formatDecimal } from "./plans";
import "./PlansPage.css";

function resolvePageLoadError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "План не найден.";
    if (err.status === 409) return "Не удалось загрузить список из-за конфликта данных. Попробуйте обновить страницу.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить список покупок.";
}

function resolveItemActionError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "Позиция не найдена. Обновите список.";
    if (err.status === 422) return "Проверьте введённые данные.";
    if (err.status === 409) return "Конфликт сохранения. Обновите список и повторите попытку.";
  }
  return err instanceof Error ? err.message : "Не удалось сохранить изменения.";
}

function resolveManualActionError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "План или позиция не найдены.";
    if (err.status === 422) return "Проверьте поля формы.";
    if (err.status === 409) return "Конфликт сохранения. Обновите список и повторите попытку.";
  }
  return err instanceof Error ? err.message : "Не удалось выполнить действие.";
}

function isNetworkUnavailableError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 0;
}

function formatOfflineSnapshotDate(rawIso: string | null): string {
  if (!rawIso) return "";
  const date = new Date(rawIso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
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

function isManualItem(item: ShoppingListItem): item is ShoppingManualItem {
  return item.is_manual === true;
}

function isComputedItem(item: ShoppingListItem): item is ShoppingComputedItem {
  return item.is_manual === false;
}

function formatManualAmount(item: ShoppingManualItem): string {
  if (item.grams === null && !item.unit) return "Количество не указано";
  if (item.grams !== null && item.unit) return `${formatDecimal(item.grams)} ${item.unit}`;
  if (item.grams !== null) return `${formatDecimal(item.grams)} г`;
  return item.unit ?? "Количество не указано";
}

export function PlanShoppingPage() {
  const { id } = useParams<{ id: string }>();
  const { isOnline } = useNetworkStatus();

  const [items, setItems] = useState<ShoppingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [offlineSnapshotSavedAt, setOfflineSnapshotSavedAt] = useState<string | null>(null);
  const [offlineNoCache, setOfflineNoCache] = useState(false);

  const [patchingFoodIds, setPatchingFoodIds] = useState<Set<number>>(new Set());
  const [draftAdjustedByFoodId, setDraftAdjustedByFoodId] = useState<Record<number, string>>({});
  const [rowErrorsByFoodId, setRowErrorsByFoodId] = useState<Record<number, string>>({});

  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [creatingManual, setCreatingManual] = useState(false);
  const [createManualError, setCreateManualError] = useState<string | null>(null);

  const [manualToDelete, setManualToDelete] = useState<ShoppingManualItem | null>(null);
  const [deletingManual, setDeletingManual] = useState(false);
  const [deleteManualError, setDeleteManualError] = useState<string | null>(null);

  const computedItems = useMemo(() => items.filter(isComputedItem), [items]);
  const manualItems = useMemo(() => items.filter(isManualItem), [items]);
  const isReadOnlyMode = !isOnline;

  const loadShoppingList = useCallback(async (options?: { background?: boolean }) => {
    if (!id) {
      setError("Некорректный идентификатор плана.");
      setLoading(false);
      return;
    }

    if (options?.background) setRefreshing(true);
    else setLoading(true);

    setError(null);
    setIsNotFound(false);
    setOfflineNoCache(false);
    try {
      const payload = await getPlanShoppingList(id);
      setItems(payload.items);
      const savedSnapshot = saveOfflineShoppingSnapshot(id, payload.items);
      setOfflineSnapshotSavedAt(savedSnapshot?.savedAt ?? null);
    } catch (err) {
      if (isNetworkUnavailableError(err)) {
        const snapshot = getOfflineShoppingSnapshot(id);
        if (snapshot) {
          setItems(snapshot.items);
          setOfflineSnapshotSavedAt(snapshot.savedAt);
        } else {
          setItems([]);
          setOfflineSnapshotSavedAt(null);
          setOfflineNoCache(true);
        }
      } else {
        setItems([]);
        setOfflineSnapshotSavedAt(null);
        if (err instanceof ApiError && err.status === 404) {
          setIsNotFound(true);
        } else {
          setError(resolvePageLoadError(err));
        }
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [id]);

  useEffect(() => {
    void loadShoppingList();
  }, [loadShoppingList]);

  useEffect(() => {
    const nextDrafts: Record<number, string> = {};
    for (const item of computedItems) {
      nextDrafts[item.food_id] = item.adjusted_grams ?? item.effective_grams;
    }
    setDraftAdjustedByFoodId(nextDrafts);
    setRowErrorsByFoodId({});
  }, [computedItems]);

  useEffect(() => {
    if (!isReadOnlyMode) return;
    setManualModalOpen(false);
    setManualToDelete(null);
  }, [isReadOnlyMode]);

  const withPatchingFoodId = async (foodId: number, action: () => Promise<void>) => {
    if (isReadOnlyMode) return;

    setPatchingFoodIds((prev) => new Set(prev).add(foodId));
    setRowErrorsByFoodId((prev) => {
      const next = { ...prev };
      delete next[foodId];
      return next;
    });
    try {
      await action();
      await loadShoppingList({ background: true });
    } catch (err) {
      setRowErrorsByFoodId((prev) => ({ ...prev, [foodId]: resolveItemActionError(err) }));
    } finally {
      setPatchingFoodIds((prev) => {
        const next = new Set(prev);
        next.delete(foodId);
        return next;
      });
    }
  };

  const handleToggleChecked = async (item: ShoppingComputedItem) => {
    if (isReadOnlyMode) return;
    await withPatchingFoodId(item.food_id, async () => {
      await patchShoppingItem(id as string, item.food_id, { checked: !item.checked });
    });
  };

  const handleSaveAdjusted = async (item: ShoppingComputedItem) => {
    if (isReadOnlyMode) return;
    const draft = draftAdjustedByFoodId[item.food_id] ?? "";
    const normalized = normalizePositiveDecimal(draft);
    if (!normalized.value) {
      setRowErrorsByFoodId((prev) => ({
        ...prev,
        [item.food_id]: normalized.error ?? "Проверьте значение количества.",
      }));
      return;
    }

    await withPatchingFoodId(item.food_id, async () => {
      await patchShoppingItem(id as string, item.food_id, { adjusted_grams: normalized.value });
    });
  };

  const handleResetAdjusted = async (item: ShoppingComputedItem) => {
    if (isReadOnlyMode) return;
    await withPatchingFoodId(item.food_id, async () => {
      await patchShoppingItem(id as string, item.food_id, { adjusted_grams: null });
    });
  };

  const handleCreateManualItem = async (payload: ShoppingManualItemCreatePayload) => {
    if (isReadOnlyMode) return;
    setCreatingManual(true);
    setCreateManualError(null);
    try {
      await createManualShoppingItem(id as string, payload);
      setManualModalOpen(false);
      await loadShoppingList({ background: true });
    } catch (err) {
      setCreateManualError(resolveManualActionError(err));
    } finally {
      setCreatingManual(false);
    }
  };

  const handleDeleteManualItem = async () => {
    if (isReadOnlyMode) return;
    if (!manualToDelete) return;

    setDeletingManual(true);
    setDeleteManualError(null);
    try {
      await deleteManualShoppingItem(id as string, manualToDelete.id);
      setManualToDelete(null);
      await loadShoppingList({ background: true });
    } catch (err) {
      setDeleteManualError(resolveManualActionError(err));
    } finally {
      setDeletingManual(false);
    }
  };

  const canShowContent = !loading && !error && !isNotFound;
  const showOfflineCachedNotice = !isOnline && offlineSnapshotSavedAt !== null;
  const showOfflineEmptyState = !isOnline && offlineNoCache && canShowContent && items.length === 0;
  const isEmpty = canShowContent && items.length === 0 && !showOfflineEmptyState;
  const offlineSnapshotLabel = formatOfflineSnapshotDate(offlineSnapshotSavedAt);

  return (
    <section className="plans-page">
      <div className="plans-shell plans-shell-wide">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Список покупок</h1>
            <p className="plans-subtitle">Позиции формируются из слотов плана и ручных добавлений.</p>
          </div>
          <div className="plans-head-actions">
            <Link to={id ? `/plans/${id}` : "/plans"} className="btn btn-secondary">
              Назад к плану
            </Link>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void loadShoppingList({ background: true })}
              disabled={loading || refreshing || isReadOnlyMode}
            >
              {isReadOnlyMode ? "Офлайн" : refreshing ? "Обновляем..." : "Обновить список"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setCreateManualError(null);
                setManualModalOpen(true);
              }}
              disabled={loading || refreshing || isReadOnlyMode}
            >
              Добавить вручную
            </button>
          </div>
        </header>

        <div className="plan-shopping-status-row">
          <p className="plan-shopping-network-status" role="status" aria-live="polite">
            <span className={`plan-shopping-network-dot ${isOnline ? "is-online" : "is-offline"}`} aria-hidden="true" />
            {isOnline ? "Онлайн" : "Офлайн"}
          </p>
          {showOfflineCachedNotice && (
            <p className="plan-shopping-offline-note">
              Вы офлайн. Показана последняя сохранённая версия списка покупок.
              {offlineSnapshotLabel ? ` Обновлено: ${offlineSnapshotLabel}.` : ""}
            </p>
          )}
        </div>

        {loading && <p className="plans-note">Загрузка списка покупок...</p>}
        {!loading && refreshing && <p className="plans-note">Обновляем данные...</p>}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => void loadShoppingList()}>
              Повторить
            </button>
          </div>
        )}

        {!loading && isNotFound && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">План не найден</p>
            <p className="plans-empty-subtitle">Возможно, план удалён или у вас нет доступа.</p>
            <Link to="/plans" className="btn btn-secondary">
              Вернуться к планам
            </Link>
          </article>
        )}

        {showOfflineEmptyState && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Вы офлайн</p>
            <p className="plans-empty-subtitle">
              Сохранённой версии списка покупок ещё нет. Откройте этот экран онлайн хотя бы один раз.
            </p>
          </article>
        )}

        {isEmpty && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Список покупок пуст</p>
            <p className="plans-empty-subtitle">Добавьте рецепты в слоты плана или добавьте ручную позицию.</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setCreateManualError(null);
                setManualModalOpen(true);
              }}
              disabled={isReadOnlyMode}
            >
              Добавить вручную
            </button>
          </article>
        )}

        {canShowContent && items.length > 0 && (
          <div className="plan-shopping-grid">
            {computedItems.length > 0 && (
              <section className="plan-shopping-card" aria-label="Позиции из рецептов">
                <h2 className="plan-shopping-section-title">Из рецептов</h2>
                <ul className="plan-shopping-list">
                  {computedItems.map((item) => {
                    const isSaving = patchingFoodIds.has(item.food_id);
                    const rowError = rowErrorsByFoodId[item.food_id];
                    const draftValue = draftAdjustedByFoodId[item.food_id] ?? item.effective_grams;
                    return (
                      <li key={`computed-${item.food_id}`} className="plan-shopping-item">
                        <div className="plan-shopping-main">
                          <div className="plan-shopping-title-row">
                            <p className="plan-shopping-name">{item.name}</p>
                            {item.brand && <p className="plan-shopping-brand">{item.brand}</p>}
                          </div>
                          <p className="plan-shopping-meta">
                            Базово: {formatDecimal(item.total_grams)} г · Текущее: {formatDecimal(item.effective_grams)} г
                          </p>
                        </div>

                        <div className="plan-shopping-controls">
                          <label className="plan-shopping-checkbox">
                            <input
                              type="checkbox"
                              checked={item.checked}
                              disabled={isSaving || isReadOnlyMode}
                              onChange={() => {
                                void handleToggleChecked(item);
                              }}
                            />
                            <span>Уже есть</span>
                          </label>

                          <div className="plan-shopping-adjust-row">
                            <input
                              className="plans-field-input plan-shopping-adjust-input"
                              type="text"
                              inputMode="decimal"
                              value={draftValue}
                              disabled={isSaving || isReadOnlyMode}
                              onChange={(event) => {
                                const next = event.target.value;
                                setDraftAdjustedByFoodId((prev) => ({ ...prev, [item.food_id]: next }));
                                setRowErrorsByFoodId((prev) => {
                                  const updated = { ...prev };
                                  delete updated[item.food_id];
                                  return updated;
                                });
                              }}
                            />
                            <button
                              type="button"
                              className="btn btn-secondary plan-shopping-inline-btn"
                              disabled={isSaving || isReadOnlyMode}
                              onClick={() => {
                                void handleSaveAdjusted(item);
                              }}
                            >
                              Сохранить
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary plan-shopping-inline-btn"
                              disabled={isSaving || item.adjusted_grams === null || isReadOnlyMode}
                              onClick={() => {
                                void handleResetAdjusted(item);
                              }}
                            >
                              Сбросить
                            </button>
                          </div>

                          {rowError && <p className="plan-shopping-row-error">{rowError}</p>}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            {manualItems.length > 0 && (
              <section className="plan-shopping-card" aria-label="Ручные позиции">
                <h2 className="plan-shopping-section-title">Добавлено вручную</h2>
                <ul className="plan-shopping-list">
                  {manualItems.map((item) => (
                    <li key={`manual-${item.id}`} className="plan-shopping-item">
                      <div className="plan-shopping-main">
                        <p className="plan-shopping-name">{item.name}</p>
                        <p className="plan-shopping-meta">{formatManualAmount(item)}</p>
                      </div>

                      <div className="plan-shopping-controls plan-shopping-controls-manual">
                        <label className="plan-shopping-checkbox">
                          <input type="checkbox" checked={item.checked} disabled />
                          <span>Уже есть</span>
                        </label>
                        <button
                          type="button"
                          className="btn btn-secondary plan-shopping-inline-btn"
                          disabled={deletingManual || manualToDelete?.id === item.id || isReadOnlyMode}
                          onClick={() => {
                            setDeleteManualError(null);
                            setManualToDelete(item);
                          }}
                        >
                          Удалить
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>

      <AddManualShoppingItemModal
        open={manualModalOpen && !isReadOnlyMode}
        saving={creatingManual}
        submitError={createManualError}
        onClose={() => {
          if (creatingManual) return;
          setManualModalOpen(false);
        }}
        onSubmit={handleCreateManualItem}
      />

      <PlanConfirmModal
        open={manualToDelete !== null}
        title="Удалить ручную позицию"
        message={manualToDelete ? `Позиция «${manualToDelete.name}» будет удалена.` : ""}
        confirmText="Удалить"
        loading={deletingManual}
        loadingText="Удаляем..."
        errorText={deleteManualError}
        onClose={() => {
          if (deletingManual) return;
          setManualToDelete(null);
        }}
        onConfirm={() => {
          void handleDeleteManualItem();
        }}
      />
    </section>
  );
}
