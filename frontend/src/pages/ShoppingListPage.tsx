import { useCallback, useEffect, useMemo, useState } from "react";
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
import { FOOD_CATEGORIES, FOOD_CATEGORY_LABELS, type FoodCategory } from "../types/foodCategory";
import type { PlanRead } from "../types/plan";
import type { ShoppingListItem, ShoppingListRead, ShoppingManualItemCreatePayload } from "../types/shopping";
import "./PlansPage.css";

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

export function ShoppingListPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

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
      try {
        const loaded = await getShoppingList(shoppingListId);
        setShoppingList(loaded);

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
        setShoppingList(null);
        setSourcePlan(null);
        setError(resolveError(err, "Список покупок не найден."));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [shoppingListId],
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

  const visibleItems = useMemo(() => shoppingList?.items.filter((item) => !item.excluded) ?? [], [shoppingList]);
  const hiddenItems = useMemo(() => shoppingList?.items.filter((item) => item.excluded) ?? [], [shoppingList]);

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
      await loadShoppingList({ background: true });
    } catch (err) {
      setRebuildError(resolveError(err, "Не удалось пересобрать список."));
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <section className="plans-page">
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
          <div className="plans-head-actions">
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
            <button type="button" className="btn btn-primary" onClick={() => setManualModalOpen(true)} disabled={!shoppingList}>
              Добавить вручную
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setDeleteListError(null);
                setDeleteListModalOpen(true);
              }}
              disabled={!shoppingList}
            >
              Удалить список
            </button>
          </div>
        </header>

        {loading && <p className="plans-note">Загрузка списка покупок...</p>}
        {!loading && refreshing && <p className="plans-note">Синхронизируем изменения...</p>}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
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
              disabled={rebuilding}
            >
              <RefreshCw aria-hidden="true" size={18} />
              {rebuilding ? "Пересобираем..." : "Пересобрать список"}
            </button>
          </article>
        )}

        {rebuildError && <Alert text={rebuildError} />}

        {!loading && !error && shoppingList && visibleItems.length === 0 && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Список пока пуст</p>
            <p className="plans-empty-subtitle">Добавьте ручные позиции или пересоберите список после заполнения плана.</p>
            <button type="button" className="btn btn-primary" onClick={() => setManualModalOpen(true)}>
              Добавить вручную
            </button>
          </article>
        )}

        {!loading && !error && shoppingList && visibleItems.length > 0 && (
          <div className="plan-shopping-grid">
            {FOOD_CATEGORIES.map((category) => {
              const categoryItems = groupedVisibleItems[category];
              if (categoryItems.length === 0) return null;
              return (
                <section key={category} className="plan-shopping-card" aria-label={FOOD_CATEGORY_LABELS[category]}>
                  <h2 className="plan-shopping-section-title">{FOOD_CATEGORY_LABELS[category]}</h2>
                  <ul className="plan-shopping-list">
                    {categoryItems.map((item) => {
                      const isSaving = patchingItemIds.has(item.id);
                      const rowError = rowErrorsByItemId[item.id];
                      const isChecked = item.checked;
                      const isManual = item.item_type === "manual";

                      return (
                        <li key={item.id} className={`plan-shopping-item ${isChecked ? "is-checked" : ""}`}>
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

                          <div className="plan-shopping-controls">
                            <label className="plan-shopping-checkbox">
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

                            {isManual ? (
                              <button
                                type="button"
                                className="btn btn-secondary plan-shopping-inline-btn"
                                disabled={isSaving}
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
                                  disabled={isSaving}
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
                                  disabled={isSaving}
                                  onClick={() => {
                                    void handleSaveAdjusted(item);
                                  }}
                                >
                                  Сохранить
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary plan-shopping-inline-btn"
                                  disabled={isSaving || item.adjusted_grams === null}
                                  onClick={() => {
                                    void handleResetAdjusted(item);
                                  }}
                                >
                                  Сбросить
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary plan-shopping-inline-btn"
                                  disabled={isSaving}
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
                </section>
              );
            })}

            {hiddenItems.length > 0 && (
              <section className="plan-shopping-card" aria-label="Скрытые позиции">
                <h2 className="plan-shopping-section-title">Скрытые позиции</h2>
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
                            disabled={isSaving}
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
        saving={creatingManual}
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
