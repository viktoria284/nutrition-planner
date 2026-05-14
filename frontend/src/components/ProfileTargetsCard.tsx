import { useEffect, useMemo, useState } from "react";
import { getFood, type FoodItem } from "../api/foods";
import { ApiError } from "../api/http";
import { deleteProfile, updateProfile, type Profile, type ProfileUpdatePayload } from "../api/profiles";
import { type FoodCategory, FOOD_CATEGORIES, FOOD_CATEGORY_LABELS } from "../types/foodCategory";
import { Alert } from "./Alert";
import { FoodSearchSelect, type FoodSearchOption } from "./FoodSearchSelect";

type GoalsMode = "kcal_pct" | "grams";

type GoalsForm = {
  target_kcal: string;
  target_protein: string;
  target_fat: string;
  target_carbs: string;
  target_fiber: string;
  protein_pct: string;
  fat_pct: string;
  carbs_pct: string;
};

type GoalsResolved = {
  target_kcal: string;
  target_protein: string;
  target_fat: string;
  target_carbs: string;
  target_fiber: string;
  protein_pct: string;
  fat_pct: string;
  carbs_pct: string;
};

type PercentTuple = {
  protein_pct: number;
  fat_pct: number;
  carbs_pct: number;
};

const DEFAULT_PCT_FORM: Pick<GoalsForm, "protein_pct" | "fat_pct" | "carbs_pct"> = {
  protein_pct: "30",
  fat_pct: "30",
  carbs_pct: "40",
};

function formatNullableNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function parseLooseNonNegativeInt(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 0) return null;
  return parsed;
}

function parsePayloadNonNegativeInt(value: string, label: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    throw new Error(`Поле "${label}" должно быть целым числом.`);
  }
  if (parsed < 0) {
    throw new Error(`Поле "${label}" не может быть отрицательным.`);
  }
  return parsed;
}

function parsePayloadFiberInt(value: string, label: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    throw new Error(`Поле "${label}" должно быть целым числом.`);
  }
  if (parsed < 0 || parsed > 100) {
    throw new Error(`Поле "${label}" должно быть в диапазоне от 0 до 100.`);
  }
  return parsed;
}


function parsePayloadNullablePositiveInt(value: string, label: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    throw new Error(`Поле "${label}" должно быть целым числом.`);
  }
  if (parsed < 1 || parsed > 1440) {
    throw new Error(`Поле "${label}" должно быть в диапазоне от 1 до 1440.`);
  }
  return parsed;
}

function calcPercentsFromGrams(
  protein: number | null,
  fat: number | null,
  carbs: number | null,
): PercentTuple | null {
  const hasAny = protein !== null || fat !== null || carbs !== null;
  if (!hasAny) return null;

  const p = protein ?? 0;
  const f = fat ?? 0;
  const c = carbs ?? 0;
  const total = (4 * p) + (9 * f) + (4 * c);

  if (total <= 0) return null;

  const proteinPct = Math.round((100 * (4 * p)) / total);
  const fatPct = Math.round((100 * (9 * f)) / total);
  const carbsPct = 100 - proteinPct - fatPct;

  return {
    protein_pct: proteinPct,
    fat_pct: fatPct,
    carbs_pct: carbsPct,
  };
}

function calcFromGrams(protein: number | null, fat: number | null, carbs: number | null) {
  const hasAny = protein !== null || fat !== null || carbs !== null;
  if (!hasAny) {
    return {
      target_kcal: "",
      protein_pct: "",
      fat_pct: "",
      carbs_pct: "",
    };
  }

  const p = protein ?? 0;
  const f = fat ?? 0;
  const c = carbs ?? 0;
  const kcal = Math.round((4 * p) + (9 * f) + (4 * c));
  const percents = calcPercentsFromGrams(protein, fat, carbs);

  return {
    target_kcal: String(kcal),
    protein_pct: percents ? String(percents.protein_pct) : "",
    fat_pct: percents ? String(percents.fat_pct) : "",
    carbs_pct: percents ? String(percents.carbs_pct) : "",
  };
}

function calcGramsFromKcalPct(
  kcal: number | null,
  proteinPct: number | null,
  fatPct: number | null,
  carbsPct: number | null,
) {
  if (kcal === null) {
    return {
      target_protein: "",
      target_fat: "",
      target_carbs: "",
    };
  }

  const protein = proteinPct === null ? null : Math.round((kcal * proteinPct) / 100 / 4);
  const fat = fatPct === null ? null : Math.round((kcal * fatPct) / 100 / 9);
  const carbs = carbsPct === null ? null : Math.round((kcal * carbsPct) / 100 / 4);

  return {
    target_protein: formatNullableNumber(protein),
    target_fat: formatNullableNumber(fat),
    target_carbs: formatNullableNumber(carbs),
  };
}

function areAllTargetsNull(profile: Profile): boolean {
  return (
    profile.target_kcal === null &&
    profile.target_protein === null &&
    profile.target_fat === null &&
    profile.target_carbs === null
  );
}

function buildGoalsForm(profile: Profile): GoalsForm {
  const percents = calcPercentsFromGrams(profile.target_protein, profile.target_fat, profile.target_carbs);

  let proteinPct = "";
  let fatPct = "";
  let carbsPct = "";

  if (percents) {
    proteinPct = String(percents.protein_pct);
    fatPct = String(percents.fat_pct);
    carbsPct = String(percents.carbs_pct);
  } else if (areAllTargetsNull(profile)) {
    proteinPct = DEFAULT_PCT_FORM.protein_pct;
    fatPct = DEFAULT_PCT_FORM.fat_pct;
    carbsPct = DEFAULT_PCT_FORM.carbs_pct;
  }

  return {
    target_kcal: formatNullableNumber(profile.target_kcal),
    target_protein: formatNullableNumber(profile.target_protein),
    target_fat: formatNullableNumber(profile.target_fat),
    target_carbs: formatNullableNumber(profile.target_carbs),
    target_fiber: formatNullableNumber(profile.target_fiber),
    protein_pct: proteinPct,
    fat_pct: fatPct,
    carbs_pct: carbsPct,
  };
}

function resolveGoalsValues(form: GoalsForm, mode: GoalsMode): GoalsResolved {
  const kcal = parseLooseNonNegativeInt(form.target_kcal);
  const protein = parseLooseNonNegativeInt(form.target_protein);
  const fat = parseLooseNonNegativeInt(form.target_fat);
  const carbs = parseLooseNonNegativeInt(form.target_carbs);
  const proteinPct = parseLooseNonNegativeInt(form.protein_pct);
  const fatPct = parseLooseNonNegativeInt(form.fat_pct);
  const carbsPct = parseLooseNonNegativeInt(form.carbs_pct);

  if (mode === "kcal_pct") {
    const grams = calcGramsFromKcalPct(kcal, proteinPct, fatPct, carbsPct);
    return {
      target_kcal: form.target_kcal,
      target_protein: grams.target_protein,
      target_fat: grams.target_fat,
      target_carbs: grams.target_carbs,
      target_fiber: form.target_fiber,
      protein_pct: form.protein_pct,
      fat_pct: form.fat_pct,
      carbs_pct: form.carbs_pct,
    };
  }

  const derived = calcFromGrams(protein, fat, carbs);
  return {
    target_kcal: derived.target_kcal,
    target_protein: form.target_protein,
    target_fat: form.target_fat,
    target_carbs: form.target_carbs,
    target_fiber: form.target_fiber,
    protein_pct: derived.protein_pct,
    fat_pct: derived.fat_pct,
    carbs_pct: derived.carbs_pct,
  };
}

function validateGoals(form: GoalsForm, mode: GoalsMode): string | null {
  const editableFields: Array<{ key: keyof GoalsForm; label: string }> =
    mode === "kcal_pct"
      ? [
          { key: "target_kcal", label: "Калории" },
          { key: "protein_pct", label: "Белки (%)" },
          { key: "fat_pct", label: "Жиры (%)" },
          { key: "carbs_pct", label: "Углеводы (%)" },
        ]
      : [
          { key: "target_protein", label: "Белки (г)" },
          { key: "target_fat", label: "Жиры (г)" },
          { key: "target_carbs", label: "Углеводы (г)" },
        ];

  for (const field of editableFields) {
    const raw = form[field.key].trim();
    if (!raw) continue;

    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
      return `Поле "${field.label}" должно быть целым числом.`;
    }
    if (parsed < 0) {
      return `Поле "${field.label}" не может быть отрицательным.`;
    }
  }

  if (mode === "kcal_pct") {
    const kcal = parseLooseNonNegativeInt(form.target_kcal);
    const proteinPct = parseLooseNonNegativeInt(form.protein_pct);
    const fatPct = parseLooseNonNegativeInt(form.fat_pct);
    const carbsPct = parseLooseNonNegativeInt(form.carbs_pct);
    const hasAnyPct = proteinPct !== null || fatPct !== null || carbsPct !== null;

    if (kcal !== null && hasAnyPct) {
      const sum = (proteinPct ?? 0) + (fatPct ?? 0) + (carbsPct ?? 0);
      if (sum !== 100) return "Сумма процентов должна быть 100%";
    }
  }

  const fiberRaw = form.target_fiber.trim();
  if (fiberRaw) {
    const fiber = Number(fiberRaw);
    if (!Number.isFinite(fiber) || !Number.isInteger(fiber)) {
      return "Поле \"Клетчатка (г)\" должно быть целым числом.";
    }
    if (fiber < 0 || fiber > 100) {
      return "Поле \"Клетчатка (г)\" должно быть в диапазоне от 0 до 100.";
    }
  }

  return null;
}


function profileFoodPlaceholder(foodId: number): FoodSearchOption {
  return { id: foodId, name: "", brand: null };
}

type GoalsValueInputProps = {
  id: string;
  ariaLabel: string;
  value: string;
  unit: string;
  editable: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
};

function GoalsValueInput({ id, ariaLabel, value, unit, editable, onChange, placeholder }: GoalsValueInputProps) {
  return (
    <div className={`goals-value ${editable ? "" : "is-readonly"}`}>
      <div className="goals-value-control">
        <input
          id={id}
          className="goals-value-field"
          aria-label={ariaLabel}
          type="number"
          min={0}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          readOnly={!editable}
          disabled={!editable}
          placeholder={placeholder}
        />
        <span className="goals-value-unit">{unit}</span>
      </div>
    </div>
  );
}

type ProfileTargetsCardProps = {
  profile: Profile;
  isDefault: boolean;
  highlighted?: boolean;
  onSaved: (updatedProfile: Profile) => void;
  onDeleted: (id: number) => void;
  onUnauthorized?: () => void;
};

export function ProfileTargetsCard({
  profile,
  isDefault,
  highlighted = false,
  onSaved,
  onDeleted,
  onUnauthorized,
}: ProfileTargetsCardProps) {
  const [mode, setMode] = useState<GoalsMode>("kcal_pct");
  const [name, setName] = useState(profile.name);
  const [goalsForm, setGoalsForm] = useState<GoalsForm>(() => buildGoalsForm(profile));
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [excludedFoods, setExcludedFoods] = useState<FoodSearchOption[]>(
    profile.excluded_food_ids.map(profileFoodPlaceholder),
  );
  const [preferredFoods, setPreferredFoods] = useState<FoodSearchOption[]>(
    profile.preferred_food_ids.map(profileFoodPlaceholder),
  );
  const [excludedFoodInputKey, setExcludedFoodInputKey] = useState(0);
  const [preferredFoodInputKey, setPreferredFoodInputKey] = useState(0);
  const [preferredCategories, setPreferredCategories] = useState<FoodCategory[]>(
    profile.preferred_categories.filter((value): value is FoodCategory =>
      FOOD_CATEGORIES.includes(value as FoodCategory),
    ),
  );
  const [maxCookTimeMinutes, setMaxCookTimeMinutes] = useState(
    profile.max_cook_time_minutes === null ? "" : String(profile.max_cook_time_minutes),
  );

  const resolvedGoals = useMemo(() => resolveGoalsValues(goalsForm, mode), [goalsForm, mode]);
  const goalsValidationError = useMemo(() => validateGoals(goalsForm, mode), [goalsForm, mode]);

  const nameValidationError = useMemo(() => {
    if (isDefault) return null;
    if (!name.trim()) return "Название профиля обязательно";
    return null;
  }, [isDefault, name]);

  const validationError = goalsValidationError ?? nameValidationError;
  const cookTimeValidationError = useMemo(() => {
    const normalized = maxCookTimeMinutes.trim();
    if (!normalized) return null;
    const parsed = Number(normalized);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 1 || parsed > 1440) {
      return "Максимальное время приготовления должно быть целым числом от 1 до 1440.";
    }
    return null;
  }, [maxCookTimeMinutes]);

  useEffect(() => {
    setName(profile.name);
    setGoalsForm(buildGoalsForm(profile));
    setMode("kcal_pct");
    setDeleteModalOpen(false);
    setDeleteError(null);
    setError(null);
    setSuccess(null);
    setExcludedFoods(profile.excluded_food_ids.map(profileFoodPlaceholder));
    setPreferredFoods(profile.preferred_food_ids.map(profileFoodPlaceholder));
    setExcludedFoodInputKey((prev) => prev + 1);
    setPreferredFoodInputKey((prev) => prev + 1);
    setPreferredCategories(
      profile.preferred_categories.filter((value): value is FoodCategory =>
        FOOD_CATEGORIES.includes(value as FoodCategory),
      ),
    );
    setMaxCookTimeMinutes(profile.max_cook_time_minutes === null ? "" : String(profile.max_cook_time_minutes));
  }, [
    profile.id,
    profile.name,
    profile.target_kcal,
    profile.target_protein,
    profile.target_fat,
    profile.target_carbs,
    profile.target_fiber,
    profile.excluded_food_ids,
    profile.preferred_food_ids,
    profile.preferred_categories,
    profile.max_cook_time_minutes,
  ]);

  useEffect(() => {
    const unresolvedIds = Array.from(
      new Set(
        [...excludedFoods, ...preferredFoods]
          .filter((option) => option.name.trim().length === 0)
          .map((option) => option.id),
      ),
    );
    if (unresolvedIds.length === 0) return undefined;

    let cancelled = false;
    type ResolvedFoodOption = {
      id: number;
      name: string;
      brand: string | null;
    };

    void Promise.all(
      unresolvedIds.map(async (foodId) => {
        try {
          const food = await getFood(foodId);
          return {
            id: foodId,
            name: food.name,
            brand: food.brand ?? null,
          } satisfies ResolvedFoodOption;
        } catch {
          return null;
        }
      }),
    ).then((resolvedOptions) => {
      if (cancelled) return;
      const resolvedById = new Map(
        resolvedOptions
          .filter((option): option is ResolvedFoodOption => option !== null)
          .map((option) => [option.id, option]),
      );

      if (resolvedById.size === 0) return;
      setExcludedFoods((prev) => prev.map((option) => resolvedById.get(option.id) ?? option));
      setPreferredFoods((prev) => prev.map((option) => resolvedById.get(option.id) ?? option));
    });

    return () => {
      cancelled = true;
    };
  }, [excludedFoods, preferredFoods]);

  useEffect(() => {
    if (!deleteModalOpen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !deleting) {
        setDeleteModalOpen(false);
        setDeleteError(null);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteModalOpen, deleting]);

  const updateGoalsField = (field: keyof GoalsForm, value: string) => {
    setGoalsForm((prev) => ({ ...prev, [field]: value }));
    setError(null);
    setSuccess(null);
  };

  const switchMode = (nextMode: GoalsMode) => {
    if (nextMode === mode) return;

    const resolved = resolveGoalsValues(goalsForm, mode);
    setGoalsForm({
      target_kcal: resolved.target_kcal,
      target_protein: resolved.target_protein,
      target_fat: resolved.target_fat,
      target_carbs: resolved.target_carbs,
      target_fiber: resolved.target_fiber,
      protein_pct: resolved.protein_pct,
      fat_pct: resolved.fat_pct,
      carbs_pct: resolved.carbs_pct,
    });
    setMode(nextMode);
    setError(null);
    setSuccess(null);
  };

  const onExcludedFoodSelected = (food: FoodItem | null) => {
    if (!food) return;
    setExcludedFoods((prev) => {
      if (prev.some((item) => item.id === food.id)) return prev;
      return [...prev, { id: food.id, name: food.name, brand: food.brand ?? null }];
    });
    setExcludedFoodInputKey((prev) => prev + 1);
    setError(null);
    setSuccess(null);
  };

  const onPreferredFoodSelected = (food: FoodItem | null) => {
    if (!food) return;
    setPreferredFoods((prev) => {
      if (prev.some((item) => item.id === food.id)) return prev;
      return [...prev, { id: food.id, name: food.name, brand: food.brand ?? null }];
    });
    setPreferredFoodInputKey((prev) => prev + 1);
    setError(null);
    setSuccess(null);
  };

  const removeExcludedFood = (foodId: number) => {
    setExcludedFoods((prev) => prev.filter((food) => food.id !== foodId));
    setError(null);
    setSuccess(null);
  };

  const removePreferredFood = (foodId: number) => {
    setPreferredFoods((prev) => prev.filter((food) => food.id !== foodId));
    setError(null);
    setSuccess(null);
  };

  const togglePreferredCategory = (category: FoodCategory) => {
    setPreferredCategories((prev) => {
      if (prev.includes(category)) {
        return prev.filter((item) => item !== category);
      }
      return [...prev, category];
    });
    setError(null);
    setSuccess(null);
  };

  const onSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validationError || saving || deleting) return;

    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      const payload: Partial<ProfileUpdatePayload> = {
        target_kcal: parsePayloadNonNegativeInt(resolvedGoals.target_kcal, "Калории"),
        target_protein: parsePayloadNonNegativeInt(resolvedGoals.target_protein, "Белки"),
        target_fat: parsePayloadNonNegativeInt(resolvedGoals.target_fat, "Жиры"),
        target_carbs: parsePayloadNonNegativeInt(resolvedGoals.target_carbs, "Углеводы"),
        target_fiber: parsePayloadFiberInt(resolvedGoals.target_fiber, "Клетчатка"),
        excluded_food_ids: excludedFoods.map((food) => food.id),
        preferred_food_ids: preferredFoods.map((food) => food.id),
        preferred_categories: preferredCategories,
        max_cook_time_minutes: parsePayloadNullablePositiveInt(
          maxCookTimeMinutes,
          "Максимальное время приготовления",
        ),
      };

      if (!isDefault) {
        payload.name = name.trim();
      }

      const updated = await updateProfile(profile.id, payload);
      onSaved(updated);
      setSuccess("Профиль сохранён.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized?.();
        return;
      }
      setError(err instanceof Error ? err.message : "Не удалось сохранить профиль.");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (isDefault || saving || deleting) return;

    setDeleteError(null);
    setDeleteModalOpen(true);
  };

  const closeDeleteModal = () => {
    if (deleting) return;
    setDeleteModalOpen(false);
    setDeleteError(null);
  };

  const onDeleteConfirmed = async () => {
    if (isDefault || saving || deleting) return;

    setError(null);
    setSuccess(null);
    setDeleteError(null);
    setDeleting(true);

    try {
      await deleteProfile(profile.id);
      setDeleteModalOpen(false);
      onDeleted(profile.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setDeleting(false);
        setDeleteModalOpen(false);
        setDeleteError(null);
        onUnauthorized?.();
        return;
      }
      setDeleteError(err instanceof Error ? err.message : "Не удалось удалить профиль.");
      setDeleting(false);
    }
  };

  const saveDisabled = saving || deleting || Boolean(validationError) || Boolean(cookTimeValidationError);

  return (
    <article id={`profile-card-${profile.id}`} className={`profile-card ${highlighted ? "is-highlighted" : ""}`}>
      <header className="profile-card-head">
        <h3 className="profile-card-title">{isDefault ? "Мой профиль" : profile.name}</h3>
        {isDefault ? (
          <span className="profile-card-badge">Основной</span>
        ) : (
          <button
            type="button"
            className="btn btn-secondary profile-delete-btn"
            onClick={onDelete}
            disabled={saving || deleting}
          >
            Удалить
          </button>
        )}
      </header>

      <label className="profile-name-field" htmlFor={`profile-name-${profile.id}`}>
        <span className="profile-name-label">Название профиля</span>
        <input
          id={`profile-name-${profile.id}`}
          className={`profile-name-input ${isDefault ? "is-readonly" : ""}`}
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setError(null);
            setSuccess(null);
          }}
          readOnly={isDefault}
          disabled={saving || deleting || isDefault}
          placeholder="Название профиля"
        />
      </label>

      {(error || validationError || cookTimeValidationError) && (
        <Alert text={error ?? validationError ?? cookTimeValidationError ?? "Ошибка"} />
      )}
      {success && <p className="settings-success">{success}</p>}

      <form className="profile-card-form" onSubmit={onSave}>
        <div className="goals-layout">
          <div className="goals-kcal-row">
            <span className="goals-kcal-label">Калории</span>
            <GoalsValueInput
              id={`target_kcal_${profile.id}`}
              ariaLabel={`Калории профиля ${profile.name}`}
              value={resolvedGoals.target_kcal}
              unit="ккал"
              editable={mode === "kcal_pct"}
              onChange={(v) => updateGoalsField("target_kcal", v)}
              placeholder="Например, 2200"
            />
          </div>

          <div className="goals-macros-card">
            <div className="goals-macros-head">
              <span>Макроэлемент</span>
              <button
                type="button"
                className={`goals-head-switch ${mode === "grams" ? "is-active" : ""}`}
                onClick={() => switchMode("grams")}
                aria-pressed={mode === "grams"}
                disabled={saving || deleting}
              >
                Граммы
              </button>
              <button
                type="button"
                className={`goals-head-switch ${mode === "kcal_pct" ? "is-active" : ""}`}
                onClick={() => switchMode("kcal_pct")}
                aria-pressed={mode === "kcal_pct"}
                disabled={saving || deleting}
              >
                Проценты
              </button>
            </div>

            <div className="goals-macros-row">
              <span className="goals-macro-name">Белки</span>
              <GoalsValueInput
                id={`target_protein_${profile.id}`}
                ariaLabel={`Белки, граммы профиля ${profile.name}`}
                value={resolvedGoals.target_protein}
                unit="г"
                editable={mode === "grams"}
                onChange={(v) => updateGoalsField("target_protein", v)}
                placeholder="130"
              />
              <GoalsValueInput
                id={`protein_pct_${profile.id}`}
                ariaLabel={`Белки, проценты профиля ${profile.name}`}
                value={resolvedGoals.protein_pct}
                unit="%"
                editable={mode === "kcal_pct"}
                onChange={(v) => updateGoalsField("protein_pct", v)}
                placeholder="30"
              />
            </div>

            <div className="goals-macros-row">
              <span className="goals-macro-name">Жиры</span>
              <GoalsValueInput
                id={`target_fat_${profile.id}`}
                ariaLabel={`Жиры, граммы профиля ${profile.name}`}
                value={resolvedGoals.target_fat}
                unit="г"
                editable={mode === "grams"}
                onChange={(v) => updateGoalsField("target_fat", v)}
                placeholder="70"
              />
              <GoalsValueInput
                id={`fat_pct_${profile.id}`}
                ariaLabel={`Жиры, проценты профиля ${profile.name}`}
                value={resolvedGoals.fat_pct}
                unit="%"
                editable={mode === "kcal_pct"}
                onChange={(v) => updateGoalsField("fat_pct", v)}
                placeholder="30"
              />
            </div>

            <div className="goals-macros-row">
              <span className="goals-macro-name">Углеводы</span>
              <GoalsValueInput
                id={`target_carbs_${profile.id}`}
                ariaLabel={`Углеводы, граммы профиля ${profile.name}`}
                value={resolvedGoals.target_carbs}
                unit="г"
                editable={mode === "grams"}
                onChange={(v) => updateGoalsField("target_carbs", v)}
                placeholder="250"
              />
              <GoalsValueInput
                id={`carbs_pct_${profile.id}`}
                ariaLabel={`Углеводы, проценты профиля ${profile.name}`}
                value={resolvedGoals.carbs_pct}
                unit="%"
                editable={mode === "kcal_pct"}
                onChange={(v) => updateGoalsField("carbs_pct", v)}
                placeholder="40"
              />
            </div>
          </div>

          <div className="goals-kcal-row">
            <span className="goals-kcal-label">Клетчатка</span>
            <GoalsValueInput
              id={`target_fiber_${profile.id}`}
              ariaLabel={`Клетчатка, граммы профиля ${profile.name}`}
              value={resolvedGoals.target_fiber}
              unit="г"
              editable
              onChange={(v) => updateGoalsField("target_fiber", v)}
              placeholder="Например, 25"
            />
          </div>
          <p className="profile-preferences-hint">
            Используется как мягкий критерий при автопланировании.
          </p>
        </div>

        <details className="profile-preferences-card">
          <summary className="profile-preferences-summary">Ограничения и предпочтения</summary>

          <label className="profile-name-field" htmlFor={`profile-max-cook-time-${profile.id}`}>
            <span className="profile-name-label">Максимальное время приготовления, мин</span>
            <input
              id={`profile-max-cook-time-${profile.id}`}
              className="profile-name-input"
              type="number"
              min={1}
              max={1440}
              step={1}
              value={maxCookTimeMinutes}
              onChange={(e) => {
                setMaxCookTimeMinutes(e.target.value);
                setError(null);
                setSuccess(null);
              }}
              placeholder="Например, 45"
              disabled={saving || deleting}
            />
            <p className="profile-preferences-hint">
              Это значение используется как ограничение по умолчанию в автоплане.
            </p>
          </label>

          <div className="profile-preferences-block">
            <span className="profile-name-label">Исключённые продукты</span>
            <FoodSearchSelect
              key={excludedFoodInputKey}
              value={null}
              onChange={onExcludedFoodSelected}
              placeholder="Добавьте продукт в исключения"
              disabled={saving || deleting}
            />
            <p className="profile-preferences-hint">Рецепты с этими продуктами не будут попадать в автоплан.</p>
            {excludedFoods.some((food) => food.name.trim().length > 0) && (
              <ul className="profile-chip-list">
                {excludedFoods
                  .filter((food) => food.name.trim().length > 0)
                  .map((food) => (
                  <li key={`excluded-${food.id}`} className="profile-chip">
                    <span className="profile-chip-label">{food.brand ? `${food.name} — ${food.brand}` : food.name}</span>
                    <button
                      type="button"
                      className="profile-chip-remove"
                      onClick={() => removeExcludedFood(food.id)}
                      disabled={saving || deleting}
                      aria-label={`Убрать ${food.name} из исключённых`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="profile-preferences-block">
            <span className="profile-name-label">Предпочитаемые продукты</span>
            <FoodSearchSelect
              key={preferredFoodInputKey}
              value={null}
              onChange={onPreferredFoodSelected}
              placeholder="Добавьте предпочитаемый продукт"
              disabled={saving || deleting}
            />
            <p className="profile-preferences-hint">Рецепты с этими продуктами будут получать приоритет.</p>
            {preferredFoods.some((food) => food.name.trim().length > 0) && (
              <ul className="profile-chip-list">
                {preferredFoods
                  .filter((food) => food.name.trim().length > 0)
                  .map((food) => (
                  <li key={`preferred-${food.id}`} className="profile-chip">
                    <span className="profile-chip-label">{food.brand ? `${food.name} — ${food.brand}` : food.name}</span>
                    <button
                      type="button"
                      className="profile-chip-remove"
                      onClick={() => removePreferredFood(food.id)}
                      disabled={saving || deleting}
                      aria-label={`Убрать ${food.name} из предпочитаемых`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="profile-preferences-block">
            <span className="profile-name-label">Предпочитаемые разделы продуктов</span>
            <div className="profile-categories-grid">
              {FOOD_CATEGORIES.map((category) => {
                const checked = preferredCategories.includes(category);
                return (
                  <label
                    key={`category-${profile.id}-${category}`}
                    className={`profile-category-chip ${checked ? "is-active" : ""}`}
                    htmlFor={`profile-category-${profile.id}-${category}`}
                  >
                    <input
                      id={`profile-category-${profile.id}-${category}`}
                      type="checkbox"
                      checked={checked}
                      onChange={() => togglePreferredCategory(category)}
                      disabled={saving || deleting}
                    />
                    {FOOD_CATEGORY_LABELS[category]}
                  </label>
                );
              })}
            </div>
          </div>
        </details>

        <div className="profile-card-actions">
          <button type="submit" className="btn btn-primary" disabled={saveDisabled}>
            {saving ? "Сохраняем..." : "Сохранить"}
          </button>
        </div>
      </form>

      {deleteModalOpen && (
        <div className="modalOverlay" role="presentation" onClick={closeDeleteModal}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`delete-profile-title-${profile.id}`}
            onClick={(e) => e.stopPropagation()}
          >
            <h4 id={`delete-profile-title-${profile.id}`} className="modalTitle">
              Удалить профиль "{profile.name}"?
            </h4>
            <p className="modalSubtitle">Действие нельзя отменить</p>

            {deleteError && <Alert text={deleteError} />}

            <div className="modalActions">
              <button type="button" className="btn btn-secondary" onClick={closeDeleteModal} disabled={deleting}>
                Отмена
              </button>
              <button type="button" className="btn btnDanger" onClick={onDeleteConfirmed} disabled={deleting}>
                {deleting ? "Удаление..." : "Удалить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
