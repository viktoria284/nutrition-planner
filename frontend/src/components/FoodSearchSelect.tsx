import { useEffect, useRef, useState } from "react";
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
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target)) setOpen(false);
    };

    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, []);

  useEffect(() => {
    const currentId = value?.id ?? null;
    if (currentId !== prevValueIdRef.current) {
      if (value) setQuery(formatFoodLabel(value));
      else if (prevValueIdRef.current !== null) setQuery("");
      prevValueIdRef.current = currentId;
    }
  }, [value]);

  useEffect(() => {
    if (!canSearch) {
      setItems([]);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

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
