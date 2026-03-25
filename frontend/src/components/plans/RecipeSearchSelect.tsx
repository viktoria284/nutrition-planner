import { useEffect, useMemo, useRef, useState } from "react";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { formatDecimal } from "../../pages/plans";
import type { DecimalValue, MealType, RecipeSource } from "../../api/recipes";

export type RecipePickerOption = {
  id: number;
  name: string;
  meal_types?: MealType[];
  servings_count?: number;
  per_serving_kcal?: DecimalValue | null;
  source?: RecipeSource | null;
};

type RecipeSearchSelectProps = {
  valueId: number | null;
  options: RecipePickerOption[];
  loading: boolean;
  error: string | null;
  disabled?: boolean;
  onChange: (recipeId: number) => void;
};

const SOURCE_LABEL: Record<RecipeSource, string> = {
  private: "Мой",
  verified: "Проверенный",
  community: "Публичный",
};

const MEAL_TYPE_LABEL: Record<MealType, string> = {
  breakfast: "Завтрак",
  lunch: "Обед",
  dinner: "Ужин",
  snack: "Перекус",
};

function formatSecondaryLine(option: RecipePickerOption): string {
  const parts: string[] = [];

  if (option.meal_types && option.meal_types.length > 0) {
    const mealTypes = option.meal_types
      .map((value) => MEAL_TYPE_LABEL[value] ?? value)
      .join(", ");
    parts.push(mealTypes);
  }

  if (typeof option.servings_count === "number") {
    parts.push(`${option.servings_count} порц.`);
  }

  if (option.per_serving_kcal !== undefined && option.per_serving_kcal !== null) {
    parts.push(`${formatDecimal(option.per_serving_kcal)} ккал/порц.`);
  }

  return parts.join(" · ");
}

export function RecipeSearchSelect({
  valueId,
  options,
  loading,
  error,
  disabled = false,
  onChange,
}: RecipeSearchSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const prevValueIdRef = useRef<number | null>(valueId);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selected = useMemo(() => options.find((option) => option.id === valueId) ?? null, [options, valueId]);
  const debouncedQuery = useDebouncedValue(query, 200);
  const normalizedQuery = debouncedQuery.trim().toLowerCase();

  useEffect(() => {
    if (valueId !== prevValueIdRef.current) {
      setQuery(selected?.name ?? "");
      prevValueIdRef.current = valueId;
      return;
    }
    if (!open && selected) setQuery(selected.name);
    if (!open && !selected && valueId === null && query.trim()) setQuery("");
  }, [open, query, selected, valueId]);

  useEffect(() => {
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, []);

  const filteredOptions = useMemo(() => {
    if (!normalizedQuery) return options;

    return options.filter((option) => {
      if (option.name.toLowerCase().includes(normalizedQuery)) return true;
      if (!option.meal_types || option.meal_types.length === 0) return false;
      return option.meal_types.some((mealType) => (MEAL_TYPE_LABEL[mealType] ?? mealType).toLowerCase().includes(normalizedQuery));
    });
  }, [normalizedQuery, options]);

  const selectedLabel = selected?.name ?? "Пусто";

  return (
    <div className="plan-recipe-picker" ref={rootRef}>
      <div className="plan-recipe-picker-input-wrap">
        <input
          className="plans-field-input plan-recipe-picker-input"
          type="search"
          value={query}
          autoComplete="off"
          placeholder="Найти рецепт"
          disabled={disabled}
          onFocus={() => {
            if (!disabled) setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
        />
      </div>

      <p className="plan-recipe-picker-selected">Выбрано: {selectedLabel}</p>

      {open && !disabled && (
        <div className="plan-recipe-picker-dropdown" role="listbox" aria-label="Результаты поиска рецептов">
          {loading && <p className="plan-recipe-picker-note">Загрузка рецептов...</p>}
          {!loading && error && <p className="plan-recipe-picker-error">{error}</p>}

          {!loading && !error && filteredOptions.length === 0 && (
            <div className="plan-recipe-picker-empty">
              <p className="plan-recipe-picker-note">Ничего не найдено.</p>
              <a className="plan-recipe-picker-create-link" href="/recipes/new" target="_blank" rel="noreferrer">
                Создать рецепт
              </a>
            </div>
          )}

          {!loading && !error && filteredOptions.length > 0 && (
            <ul className="plan-recipe-picker-list">
              {filteredOptions.map((option) => {
                const secondaryLine = formatSecondaryLine(option);
                const isSelected = option.id === valueId;

                return (
                  <li key={option.id} className="plan-recipe-picker-row">
                    <button
                      type="button"
                      className={`plan-recipe-picker-item ${isSelected ? "is-selected" : ""}`}
                      onClick={() => {
                        onChange(option.id);
                        setQuery(option.name);
                        setOpen(false);
                      }}
                    >
                      <span className="plan-recipe-picker-item-main">
                        <span className="plan-recipe-picker-item-name">{option.name}</span>
                        {option.source && <span className="plan-recipe-picker-source">{SOURCE_LABEL[option.source] ?? option.source}</span>}
                      </span>

                      {secondaryLine && <span className="plan-recipe-picker-item-secondary">{secondaryLine}</span>}
                    </button>

                    <a
                      className="plan-recipe-picker-open-link"
                      href={`/recipes/${option.id}`}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(event) => {
                        event.stopPropagation();
                      }}
                    >
                      Открыть
                    </a>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
