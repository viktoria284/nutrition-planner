import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { searchFoods, type FoodItem } from "../api/foods";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import "./FoodSearchSelect.css";

export type FoodSearchOption = Pick<FoodItem, "id" | "name" | "brand">;

type FoodSearchSelectProps = {
  value?: FoodSearchOption | null;
  onChange: (food: FoodItem | null) => void;
  placeholder?: string;
  disabled?: boolean;
  allowCreate?: boolean;
};

function formatFoodLabel(food: FoodSearchOption): string {
  return food.brand ? `${food.name} — ${food.brand}` : food.name;
}

export function FoodSearchSelect({
  value = null,
  onChange,
  placeholder = "Начните вводить название продукта",
  disabled = false,
  allowCreate = false,
}: FoodSearchSelectProps) {
  const location = useLocation();
  const [query, setQuery] = useState(value ? formatFoodLabel(value) : "");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<FoodItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const prevValueIdRef = useRef<number | null>(value?.id ?? null);

  const debouncedQuery = useDebouncedValue(query, 350);
  const normalizedQuery = debouncedQuery.trim();
  const canSearch = normalizedQuery.length >= 2;

  useEffect(() => {
    if (!open) return undefined;

    const close = () => setOpen(false);
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target)) close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onScroll = (event: Event) => {
      const target = event.target as Node | null;
      if (target && rootRef.current?.contains(target)) return;
      close();
    };
    const onTouchMove = (event: TouchEvent) => {
      const target = event.target as Node | null;
      if (target && rootRef.current?.contains(target)) return;
      close();
    };

    window.addEventListener("pointerdown", onPointerDown, true);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", onPointerDown, true);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("touchmove", onTouchMove);
    };
  }, [open]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setOpen(false), 0);
    return () => window.clearTimeout(timeoutId);
  }, [location.pathname, location.search]);

  useEffect(() => {
    const currentId = value?.id ?? null;
    if (currentId !== prevValueIdRef.current) {
      const previousId = prevValueIdRef.current;
      prevValueIdRef.current = currentId;
      const nextQuery = value ? formatFoodLabel(value) : previousId !== null ? "" : null;
      if (nextQuery === null) return;
      const timeoutId = window.setTimeout(() => setQuery(nextQuery), 0);
      return () => window.clearTimeout(timeoutId);
    }
  }, [value]);

  useEffect(() => {
    if (!canSearch) {
      const timeoutId = window.setTimeout(() => {
        setItems([]);
        setError(null);
        setLoading(false);
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    let cancelled = false;
    const loadingTimeoutId = window.setTimeout(() => {
      if (cancelled) return;
      setLoading(true);
      setError(null);
    }, 0);

    searchFoods({ q: normalizedQuery, limit: 20 })
      .then((results) => {
        if (cancelled) return;
        setItems(results);
      })
      .catch((err) => {
        if (cancelled) return;
        setItems([]);
        setError(err instanceof Error ? err.message : "Не удалось загрузить результаты.");
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
      window.clearTimeout(loadingTimeoutId);
    };
  }, [normalizedQuery, canSearch]);

  const onInputChange = (nextValue: string) => {
    setQuery(nextValue);
    setOpen(true);
    setError(null);

    if (!nextValue.trim()) {
      onChange(null);
      setItems([]);
      setLoading(false);
    }
  };

  const onSelectFood = (food: FoodItem) => {
    onChange(food);
    setQuery(formatFoodLabel(food));
    setOpen(false);
    setError(null);
    setItems([]);
  };

  return (
    <div className="food-search-select" ref={rootRef}>
      <input
        className="food-search-select-input"
        type="search"
        value={query}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        onFocus={() => {
          if (!disabled) setOpen(true);
        }}
        onChange={(e) => onInputChange(e.target.value)}
      />

      {open && !disabled && (
        <div className="food-search-select-dropdown" role="listbox" aria-label="Результаты поиска продуктов">
          {!canSearch && <p className="food-search-select-note">Введите минимум 2 символа</p>}
          {canSearch && loading && <p className="food-search-select-note">Загрузка...</p>}
          {canSearch && !loading && error && <p className="food-search-select-error">{error}</p>}

          {canSearch && !loading && !error && items.length === 0 && (
            <div className="food-search-select-empty">
              <p className="food-search-select-note">Ничего не найдено</p>
              {allowCreate && (
                <p className="food-search-select-note">Можно создать продукт через кнопку "Добавить продукт".</p>
              )}
            </div>
          )}

          {canSearch && !loading && !error && items.length > 0 && (
            <ul className="food-search-select-list">
              {items.map((food) => (
                <li key={food.id}>
                  <button type="button" className="food-search-select-item" onClick={() => onSelectFood(food)}>
                    <span className="food-search-select-item-name">{food.name}</span>
                    {food.brand && <span className="food-search-select-item-brand">{food.brand}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
