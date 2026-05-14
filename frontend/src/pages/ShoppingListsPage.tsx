import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/http";
import { bulkDeleteShoppingLists, deleteShoppingList, listShoppingLists, mergeShoppingLists } from "../api/shopping";
import { Alert } from "../components/Alert";
import { PlanConfirmModal } from "../components/plans/PlanConfirmModal";
import type { ShoppingListSummary } from "../types/shopping";
import "./PlansPage.css";

function resolveShoppingListsError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Нужно снова войти в аккаунт.";
    if (err.status === 404) return "Список покупок не найден.";
    if (err.status === 422) return "Проверьте выбранные списки.";
  }
  return err instanceof Error ? err.message : "Не удалось загрузить списки покупок.";
}

function formatDateTimeRu(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatItemsCount(count: number): string {
  const abs = Math.abs(count);
  const mod10 = abs % 10;
  const mod100 = abs % 100;

  if (mod10 === 1 && mod100 !== 11) return `${count} позиция`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} позиции`;
  return `${count} позиций`;
}

export function ShoppingListsPage() {
  const navigate = useNavigate();
  const [lists, setLists] = useState<ShoppingListSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [listToDelete, setListToDelete] = useState<ShoppingListSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [bulkDeleteIds, setBulkDeleteIds] = useState<number[]>([]);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkDeleteError, setBulkDeleteError] = useState<string | null>(null);

  const [mergeModalOpen, setMergeModalOpen] = useState(false);
  const [mergeTitle, setMergeTitle] = useState("Общий список покупок");
  const [merging, setMerging] = useState(false);
  const [mergeError, setMergeError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listShoppingLists()
      .then((items) => {
        if (cancelled) return;
        setLists(items);
      })
      .catch((err) => {
        if (cancelled) return;
        setLists([]);
        setError(resolveShoppingListsError(err));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setSelectedIds((prev) => {
      const availableIds = new Set(lists.map((list) => list.id));
      const next = new Set([...prev].filter((id) => availableIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [lists]);

  const sortedLists = useMemo(
    () =>
      [...lists].sort((a, b) => {
        const first = new Date(a.generated_at || a.created_at).getTime();
        const second = new Date(b.generated_at || b.created_at).getTime();
        return second - first;
      }),
    [lists],
  );

  const selectedCount = selectedIds.size;

  const toggleSelected = (listId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(listId)) next.delete(listId);
      else next.add(listId);
      return next;
    });
  };

  const handleDeleteList = async () => {
    if (!listToDelete) return;

    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteShoppingList(listToDelete.id);
      setLists((prev) => prev.filter((list) => list.id !== listToDelete.id));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(listToDelete.id);
        return next;
      });
      setListToDelete(null);
    } catch (err) {
      setDeleteError(resolveShoppingListsError(err));
    } finally {
      setDeleting(false);
    }
  };

  const openBulkDeleteModal = () => {
    if (selectedIds.size === 0) return;
    setBulkDeleteIds([...selectedIds]);
    setBulkDeleteError(null);
  };

  const handleBulkDelete = async () => {
    if (bulkDeleteIds.length === 0) return;

    setBulkDeleting(true);
    setBulkDeleteError(null);
    try {
      await bulkDeleteShoppingLists({ shopping_list_ids: bulkDeleteIds });
      const deleted = new Set(bulkDeleteIds);
      setLists((prev) => prev.filter((list) => !deleted.has(list.id)));
      setSelectedIds(new Set());
      setBulkDeleteIds([]);
    } catch (err) {
      setBulkDeleteError(resolveShoppingListsError(err));
    } finally {
      setBulkDeleting(false);
    }
  };

  const openMergeModal = () => {
    setMergeTitle("Общий список покупок");
    setMergeError(null);
    setMergeModalOpen(true);
  };

  const closeMergeModal = () => {
    if (merging) return;
    setMergeModalOpen(false);
    setMergeError(null);
  };

  const handleMergeSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedIds.size < 2) {
      setMergeError("Выберите минимум два списка для объединения.");
      return;
    }

    setMerging(true);
    setMergeError(null);
    try {
      const merged = await mergeShoppingLists({
        shopping_list_ids: [...selectedIds],
        title: mergeTitle.trim() || undefined,
      });
      setMergeModalOpen(false);
      setSelectedIds(new Set());
      navigate(`/shopping-lists/${merged.id}`);
    } catch (err) {
      setMergeError(resolveShoppingListsError(err));
    } finally {
      setMerging(false);
    }
  };

  return (
    <section className="plans-page">
      <div className="plans-shell plans-shell-wide">
        <header className="plans-head">
          <div className="plans-head-main">
            <h1 className="plans-title">Списки покупок</h1>
            <p className="plans-subtitle">
              Списки формируются на основе планов питания и могут быть пересобраны при изменении плана.
            </p>
          </div>
          <div className="plans-head-actions">
            <button type="button" className="btn btn-secondary" disabled={selectedCount < 2} onClick={openMergeModal}>
              Объединить
            </button>
            <button type="button" className="btn btn-secondary" disabled={selectedCount < 1} onClick={openBulkDeleteModal}>
              Удалить выбранные
            </button>
            <Link to="/plans" className="btn btn-primary">
              Перейти к планам
            </Link>
          </div>
        </header>

        {loading && <p className="plans-note">Загрузка списков покупок...</p>}

        {!loading && error && (
          <div className="plans-error-block">
            <Alert text={error} />
          </div>
        )}

        {!loading && !error && sortedLists.length === 0 && (
          <article className="plans-empty-card">
            <p className="plans-empty-title">Пока нет списков покупок.</p>
            <p className="plans-empty-subtitle">Соберите список из плана питания.</p>
            <Link to="/plans" className="btn btn-primary">
              Перейти к планам
            </Link>
          </article>
        )}

        {!loading && !error && sortedLists.length > 0 && (
          <>
            <div className="shopping-lists-toolbar" aria-live="polite">
              <span>{selectedCount > 0 ? `Выбрано: ${selectedCount}` : "Выберите списки, чтобы объединить их."}</span>
            </div>

            <ul className="plans-list">
              {sortedLists.map((list) => {
                const isSelected = selectedIds.has(list.id);
                const sourceLabel =
                  list.source_plan_ids.length > 1 ? "Источник: несколько планов питания" : "Источник: план питания";

                return (
                  <li key={list.id} className={`plan-list-item shopping-list-card ${isSelected ? "is-selected" : ""}`}>
                    <label className="shopping-list-card-select">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        aria-label={`Выбрать список «${list.title}»`}
                        onChange={() => toggleSelected(list.id)}
                      />
                      <span className="sr-only">Выбрать список</span>
                    </label>

                    <Link to={`/shopping-lists/${list.id}`} className="plan-list-main plan-list-main-link">
                      <div className="shopping-list-card-title-row">
                        <p className="plan-list-title">{list.title}</p>
                        {list.is_outdated && (
                          <span className="shopping-list-status-badge is-outdated">Требует пересборки</span>
                        )}
                      </div>
                      <div className="plan-list-meta">
                        <span>{formatDateTimeRu(list.generated_at || list.created_at)}</span>
                        <span>{formatItemsCount(list.items_total)}</span>
                        <span>{sourceLabel}</span>
                      </div>
                    </Link>

                    <div className="plan-list-actions shopping-list-card-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={deleting && listToDelete?.id === list.id}
                        onClick={() => {
                          setDeleteError(null);
                          setListToDelete(list);
                        }}
                      >
                        Удалить
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>

      {mergeModalOpen && (
        <div
          className="plans-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) closeMergeModal();
          }}
        >
          <div className="plans-modal" role="dialog" aria-modal="true" aria-labelledby="merge-shopping-modal-title">
            <header className="plans-modal-head">
              <h2 id="merge-shopping-modal-title" className="plans-modal-title">
                Объединить списки покупок
              </h2>
              <p className="plans-modal-subtitle">
                Будет создан новый список. Уже отмеченные и скрытые позиции не попадут в объединённый список.
              </p>
            </header>

            {mergeError && <Alert text={mergeError} />}

            <form className="plans-modal-form" onSubmit={handleMergeSubmit} noValidate>
              <label className="plans-field">
                <span className="plans-field-label">Название нового списка</span>
                <input
                  className="plans-field-input"
                  type="text"
                  value={mergeTitle}
                  disabled={merging}
                  onChange={(event) => {
                    setMergeTitle(event.target.value);
                    setMergeError(null);
                  }}
                />
              </label>

              <div className="plans-modal-actions">
                <button type="button" className="btn btn-secondary" onClick={closeMergeModal} disabled={merging}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={merging || selectedCount < 2}>
                  {merging ? "Объединяем..." : "Создать общий список"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <PlanConfirmModal
        open={listToDelete !== null}
        title="Удалить список покупок?"
        message="Список будет удалён без возможности восстановления."
        confirmText="Удалить"
        loading={deleting}
        loadingText="Удаляем..."
        errorText={deleteError}
        onClose={() => {
          if (deleting) return;
          setListToDelete(null);
        }}
        onConfirm={() => {
          void handleDeleteList();
        }}
      />

      <PlanConfirmModal
        open={bulkDeleteIds.length > 0}
        title={bulkDeleteIds.length === 1 ? "Удалить выбранный список?" : "Удалить выбранные списки?"}
        message={
          bulkDeleteIds.length === 1
            ? "Список будет удалён без возможности восстановления."
            : `Будет удалено списков: ${bulkDeleteIds.length}. Действие нельзя отменить.`
        }
        confirmText="Удалить"
        loading={bulkDeleting}
        loadingText="Удаляем..."
        errorText={bulkDeleteError}
        onClose={() => {
          if (bulkDeleting) return;
          setBulkDeleteIds([]);
          setBulkDeleteError(null);
        }}
        onConfirm={() => {
          void handleBulkDelete();
        }}
      />
    </section>
  );
}
