import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  deleteRecipeCoverImage,
  deleteRecipeStepImage,
  getRecipe,
  replaceRecipeSteps,
  resolveRecipeImageSrc,
  updateRecipe,
  uploadRecipeCoverImage,
  uploadRecipeStepImage,
  type MealType,
  type RecipeStepInput,
  type RecipeStepRead,
  type RecipeRead,
} from "../api/recipes";
import { Alert } from "../components/Alert";
import { FormErrorSummary } from "../components/FormErrorSummary";
import { MarkdownTextarea } from "../components/MarkdownTextarea";
import {
  RECIPE_MEAL_TYPE_OPTIONS,
  toRecipeFormState,
  type RecipeFormErrors,
  type RecipeFormState,
  validateRecipeForm,
} from "./recipeForm";
import "./RecipesPage.css";

type StepDraft = {
  localId: string;
  id?: number;
  text: string;
  note: string;
  image_url: string | null;
};

let stepLocalCounter = 0;

function nextStepLocalId() {
  stepLocalCounter += 1;
  return `step-${Date.now()}-${stepLocalCounter}`;
}

function getCoverUploadErrorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return err instanceof Error ? err.message : "Не удалось загрузить фото блюда.";
  }
  if (err.status === 413) {
    return "Файл слишком большой. Максимальный размер — 5 МБ.";
  }
  const message = String(err.message || "").toLowerCase();
  if (err.status === 422 && (message.includes("unsupported image type") || message.includes("image type"))) {
    return "Поддерживаются JPG, PNG и WEBP до 5 МБ.";
  }
  return err.message || "Не удалось загрузить фото блюда.";
}

function toStepDrafts(steps: RecipeStepRead[] | undefined): StepDraft[] {
  return (steps ?? [])
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((step) => ({
      localId: nextStepLocalId(),
      id: step.id,
      text: step.text,
      note: step.note ?? "",
      image_url: step.image_url,
    }));
}

export function RecipeEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [recipe, setRecipe] = useState<RecipeRead | null>(null);
  const [form, setForm] = useState<RecipeFormState | null>(null);
  const [steps, setSteps] = useState<StepDraft[]>([]);
  const [stepFiles, setStepFiles] = useState<Record<string, File | null>>({});

  const [errors, setErrors] = useState<RecipeFormErrors>({ form: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [coverUploading, setCoverUploading] = useState(false);
  const [coverError, setCoverError] = useState<string | null>(null);
  const [coverSuccess, setCoverSuccess] = useState<string | null>(null);

  const [stepsSaving, setStepsSaving] = useState(false);
  const [stepsError, setStepsError] = useState<string | null>(null);
  const [stepsSuccess, setStepsSuccess] = useState<string | null>(null);
  const isStepInteractionDisabled = stepsSaving || submitting;

  const recipeId = useMemo(() => Number(id), [id]);

  const loadRecipe = useCallback(async () => {
    if (!id || !Number.isInteger(recipeId) || recipeId < 1) {
      setForm(null);
      setRecipe(null);
      setSteps([]);
      setLoading(false);
      setError("Некорректный идентификатор рецепта.");
      return;
    }

    setLoading(true);
    setError(null);
    setErrors({ form: [] });

    try {
      const loaded = await getRecipe(recipeId);
      setRecipe(loaded);
      setForm(toRecipeFormState(loaded));
      setSteps(toStepDrafts(loaded.steps));
      setStepFiles({});
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Рецепт не найден.");
      } else {
        setError(err instanceof Error ? err.message : "Не удалось загрузить рецепт.");
      }
      setForm(null);
      setRecipe(null);
      setSteps([]);
    } finally {
      setLoading(false);
    }
  }, [id, recipeId]);

  useEffect(() => {
    void loadRecipe();
  }, [loadRecipe]);

  useEffect(() => {
    if (!coverSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setCoverSuccess(null), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [coverSuccess]);

  useEffect(() => {
    if (!stepsSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setStepsSuccess(null), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [stepsSuccess]);

  const updateField = (field: keyof Omit<RecipeFormState, "meal_types">, value: string) => {
    setForm((prev) => (prev ? { ...prev, [field]: value } : prev));
    setErrors((prev) => ({ ...prev, [field]: undefined, form: [] }));
  };

  const toggleMealType = (mealType: MealType) => {
    setForm((prev) => {
      if (!prev) return prev;
      const meal_types = prev.meal_types.includes(mealType)
        ? prev.meal_types.filter((value) => value !== mealType)
        : [...prev.meal_types, mealType];

      return { ...prev, meal_types };
    });
    setErrors((prev) => ({ ...prev, meal_types: undefined, form: [] }));
  };

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form || !id || !Number.isInteger(recipeId) || recipeId < 1) {
      setErrors({ form: ["Некорректный идентификатор рецепта."] });
      return;
    }

    const { errors: validationErrors, payload } = validateRecipeForm(form);
    if (!payload) {
      setErrors(validationErrors);
      return;
    }

    const invalidStep = steps.find((step) => !step.text.trim());
    if (invalidStep) {
      setStepsError("У каждого шага должно быть описание.");
      setErrors({ form: ["Исправьте шаги приготовления перед сохранением."] });
      return;
    }

    setSubmitting(true);
    setErrors({ form: [] });
    setStepsError(null);

    try {
      await updateRecipe(recipeId, payload);
      const stepsPayload: RecipeStepInput[] = steps.map((step, index) => ({
        id: step.id,
        text: step.text,
        note: step.note.trim() || null,
        position: index + 1,
      }));
      const savedSteps = await replaceRecipeSteps(recipeId, stepsPayload);
      setSteps(toStepDrafts(savedSteps));
      setStepFiles({});
      navigate(`/recipes/${recipeId}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErrors({ form: ["Этот рецепт нельзя редактировать (только private draft)."] });
      } else if (err instanceof ApiError && err.status === 404) {
        setErrors({ form: ["Рецепт не найден."] });
      } else {
        setErrors({ form: [err instanceof Error ? err.message : "Не удалось сохранить рецепт и шаги."] });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onUploadCover = async () => {
    if (!recipe || !fileInputRef.current?.files?.[0]) return;
    const file = fileInputRef.current.files[0];
    setCoverUploading(true);
    setCoverError(null);
    setCoverSuccess(null);
    try {
      const updated = await uploadRecipeCoverImage(recipe.id, file);
      setRecipe(updated);
      setForm(toRecipeFormState(updated));
      if (fileInputRef.current) fileInputRef.current.value = "";
      setCoverSuccess("Фото блюда обновлено.");
    } catch (err) {
      setCoverError(getCoverUploadErrorMessage(err));
    } finally {
      setCoverUploading(false);
    }
  };

  const onDeleteCover = async () => {
    if (!recipe) return;
    setCoverUploading(true);
    setCoverError(null);
    setCoverSuccess(null);
    try {
      const updated = await deleteRecipeCoverImage(recipe.id);
      setRecipe(updated);
      setForm(toRecipeFormState(updated));
      setCoverSuccess("Фото блюда удалено.");
    } catch (err) {
      setCoverError(err instanceof Error ? err.message : "Не удалось удалить фото.");
    } finally {
      setCoverUploading(false);
    }
  };

  const addStep = () => {
    setSteps((prev) => [
      ...prev,
      {
        localId: nextStepLocalId(),
        text: "",
        note: "",
        image_url: null,
      },
    ]);
    setStepsError(null);
  };

  const updateStep = (localId: string, patch: Partial<StepDraft>) => {
    setSteps((prev) => prev.map((step) => (step.localId === localId ? { ...step, ...patch } : step)));
    setStepsError(null);
  };

  const removeStep = (localId: string) => {
    setSteps((prev) => prev.filter((step) => step.localId !== localId));
    setStepFiles((prev) => {
      const next = { ...prev };
      delete next[localId];
      return next;
    });
    setStepsError(null);
  };

  const moveStep = (localId: string, direction: -1 | 1) => {
    setSteps((prev) => {
      const index = prev.findIndex((step) => step.localId === localId);
      if (index < 0) return prev;
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= prev.length) return prev;
      const next = [...prev];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
    setStepsError(null);
  };

  const uploadStepImage = async (localId: string) => {
    if (!recipe) return;
    const step = steps.find((item) => item.localId === localId);
    const file = stepFiles[localId];
    if (!step?.id || !file) {
      setStepsError("Сохраните рецепт, чтобы добавить фото к этому шагу.");
      return;
    }

    setStepsSaving(true);
    setStepsError(null);
    setStepsSuccess(null);
    try {
      const saved = await uploadRecipeStepImage(recipe.id, step.id, file);
      setSteps((prev) => prev.map((item) => (item.localId === localId ? { ...item, image_url: saved.image_url } : item)));
      setStepFiles((prev) => ({ ...prev, [localId]: null }));
      setStepsSuccess("Фото шага загружено.");
    } catch (err) {
      setStepsError(err instanceof Error ? err.message : "Не удалось загрузить фото шага.");
    } finally {
      setStepsSaving(false);
    }
  };

  const removeStepImage = async (localId: string) => {
    if (!recipe) return;
    const step = steps.find((item) => item.localId === localId);
    if (!step?.id) return;

    setStepsSaving(true);
    setStepsError(null);
    setStepsSuccess(null);
    try {
      const saved = await deleteRecipeStepImage(recipe.id, step.id);
      setSteps((prev) => prev.map((item) => (item.localId === localId ? { ...item, image_url: saved.image_url } : item)));
      setStepsSuccess("Фото шага удалено.");
    } catch (err) {
      setStepsError(err instanceof Error ? err.message : "Не удалось удалить фото шага.");
    } finally {
      setStepsSaving(false);
    }
  };

  return (
    <section className="recipes-page">
      <div className="recipes-shell">
        <header className="recipes-head">
          <div className="recipes-head-main">
            <h1 className="recipes-title">Редактирование рецепта</h1>
          </div>

          <div className="recipes-head-actions">
            <Link to={id ? `/recipes/${id}` : "/recipes"} className="btn btn-secondary">
              Назад
            </Link>
          </div>
        </header>

        {loading && <p className="recipes-note">Загрузка...</p>}

        {!loading && error && (
          <div className="recipes-error-block">
            <Alert text={error} />
            <button type="button" className="btn btn-secondary" onClick={() => void loadRecipe()}>
              Повторить
            </button>
          </div>
        )}

        {!loading && !error && form && recipe && (
          <>
            <form className="recipes-form" onSubmit={onSubmit} noValidate>
              <FormErrorSummary
                messages={errors.form}
                className="form-error-summary recipes-form-summary"
                itemClassName="recipes-form-error-item"
              />

              <label className="recipes-field" htmlFor="recipe_name">
                <span className="recipes-field-label">Название</span>
                <input
                  id="recipe_name"
                  className={`recipes-field-input ${errors.name ? "is-invalid" : ""}`}
                  type="text"
                  value={form.name}
                  onChange={(e) => updateField("name", e.target.value)}
                  placeholder="Например, Омлет с овощами"
                  autoFocus
                  disabled={submitting}
                />
                <div className="recipes-field-error-slot" aria-live="polite">
                  {errors.name && <p className="recipes-field-error">{errors.name}</p>}
                </div>
              </label>

              <label className="recipes-field" htmlFor="recipe_description">
                <span className="recipes-field-label">Описание (опционально)</span>
                <textarea
                  id="recipe_description"
                  className="recipes-field-textarea"
                  value={form.description}
                  onChange={(e) => updateField("description", e.target.value)}
                  placeholder="Короткое описание рецепта"
                  disabled={submitting}
                />
              </label>

              <MarkdownTextarea
                id="recipe_instructions"
                label="Общие инструкции (опционально)"
                value={form.instructions}
                onChange={(next) => updateField("instructions", next)}
                placeholder="Например, как подготовить ингредиенты до шагов"
                disabled={submitting}
                rows={4}
              />

              <label className="recipes-field" htmlFor="recipe_servings_count">
                <span className="recipes-field-label">Количество порций</span>
                <input
                  id="recipe_servings_count"
                  className={`recipes-field-input ${errors.servings_count ? "is-invalid" : ""}`}
                  type="number"
                  min={1}
                  step={1}
                  value={form.servings_count}
                  onChange={(e) => updateField("servings_count", e.target.value)}
                  disabled={submitting}
                />
                <div className="recipes-field-error-slot" aria-live="polite">
                  {errors.servings_count && <p className="recipes-field-error">{errors.servings_count}</p>}
                </div>
              </label>

              <label className="recipes-field" htmlFor="recipe_cook_time_minutes">
                <span className="recipes-field-label">Время приготовления, мин</span>
                <input
                  id="recipe_cook_time_minutes"
                  className={`recipes-field-input ${errors.cook_time_minutes ? "is-invalid" : ""}`}
                  type="number"
                  min={1}
                  max={1440}
                  step={1}
                  value={form.cook_time_minutes}
                  onChange={(e) => updateField("cook_time_minutes", e.target.value)}
                  placeholder="Например, 25"
                  disabled={submitting}
                />
                <div className="recipes-field-error-slot" aria-live="polite">
                  {errors.cook_time_minutes && <p className="recipes-field-error">{errors.cook_time_minutes}</p>}
                </div>
              </label>

              <div className="recipes-field">
                <span className="recipes-field-label">Тип приёма пищи</span>
                <div className="recipes-meal-grid">
                  {RECIPE_MEAL_TYPE_OPTIONS.map((mealType) => {
                    const checked = form.meal_types.includes(mealType.value);
                    return (
                      <label
                        key={mealType.value}
                        htmlFor={`meal-type-${mealType.value}`}
                        className={`recipes-meal-checkbox ${checked ? "is-active" : ""}`}
                      >
                        <input
                          id={`meal-type-${mealType.value}`}
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleMealType(mealType.value)}
                          disabled={submitting}
                        />
                        {mealType.label}
                      </label>
                    );
                  })}
                </div>
                <div className="recipes-field-error-slot" aria-live="polite">
                  {errors.meal_types && <p className="recipes-field-error">{errors.meal_types}</p>}
                </div>
              </div>

              <div className="recipes-form-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => navigate(id ? `/recipes/${id}` : "/recipes")}
                  disabled={submitting}
                >
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Сохраняем..." : "Сохранить рецепт"}
                </button>
              </div>
            </form>

            <article className="recipe-card">
              <h2 className="recipe-metrics-title">Фото блюда</h2>
              {coverError && <Alert text={coverError} />}
              {coverSuccess && <p className="recipes-inline-success">{coverSuccess}</p>}
              <div className="recipe-cover-edit-grid">
                <div className="recipe-cover">
                  {recipe.image_url ? (
                    <img src={resolveRecipeImageSrc(recipe.image_url) ?? undefined} alt={`Фото блюда: ${recipe.name}`} className="recipe-cover-image" />
                  ) : (
                    <div className="recipe-cover-fallback" aria-hidden="true">
                      {recipe.name.slice(0, 1).toUpperCase()}
                    </div>
                  )}
                </div>
                <div className="recipes-field">
                  <input
                    ref={fileInputRef}
                    className="recipes-field-input"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={coverUploading}
                  />
                  <p className="recipes-field-hint">Поддерживаются JPG, PNG и WEBP до 5 МБ.</p>
                  <div className="recipes-form-actions recipes-form-actions-start">
                    <button type="button" className="btn btn-primary" onClick={() => void onUploadCover()} disabled={coverUploading}>
                      {coverUploading ? "Загружаем..." : "Загрузить фото"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void onDeleteCover()}
                      disabled={coverUploading || !recipe.image_url}
                    >
                      Удалить фото
                    </button>
                  </div>
                </div>
              </div>
            </article>

            <article className="recipe-card">
              <div className="recipe-steps-head">
                <h2 className="recipe-metrics-title">Шаги приготовления</h2>
              </div>

              {stepsError && <Alert text={stepsError} />}
              {stepsSuccess && <p className="recipes-inline-success">{stepsSuccess}</p>}

              {steps.length === 0 && <p className="recipes-note">Шаги пока не добавлены.</p>}

              {steps.length > 0 && (
                <div className="recipe-steps-list">
                  {steps.map((step, index) => (
                    <section key={step.localId} className="recipe-step-card">
                      <div className="recipe-step-head">
                        <h3 className="recipe-step-title">Шаг {index + 1}</h3>
                        <div className="recipe-step-actions">
                          <button type="button" className="btn btn-secondary" onClick={() => moveStep(step.localId, -1)} disabled={isStepInteractionDisabled || index === 0}>
                            Вверх
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => moveStep(step.localId, 1)}
                            disabled={isStepInteractionDisabled || index === steps.length - 1}
                          >
                            Вниз
                          </button>
                          <button type="button" className="btn btn-subtle" onClick={() => removeStep(step.localId)} disabled={isStepInteractionDisabled}>
                            Удалить
                          </button>
                        </div>
                      </div>

                      <MarkdownTextarea
                        id={`step-text-${step.localId}`}
                        label="Описание шага"
                        value={step.text}
                        onChange={(next) => updateStep(step.localId, { text: next })}
                        placeholder="Опишите, что нужно сделать на этом шаге"
                        disabled={isStepInteractionDisabled}
                        rows={3}
                        compact
                        textareaClassName="recipe-step-text-input"
                      />

                      <MarkdownTextarea
                        id={`step-note-${step.localId}`}
                        label="Совет или примечание (опционально)"
                        value={step.note}
                        onChange={(next) => updateStep(step.localId, { note: next })}
                        placeholder="Например, как улучшить вкус или ускорить процесс"
                        disabled={isStepInteractionDisabled}
                        rows={2}
                        compact
                        textareaClassName="recipe-step-note-input"
                      />

                      <div className="recipe-step-image-grid">
                        <div className="recipe-step-image-preview">
                          {step.image_url ? (
                            <img src={resolveRecipeImageSrc(step.image_url) ?? undefined} alt={`Шаг ${index + 1}`} className="recipe-cover-image" />
                          ) : (
                            <div className="recipe-cover-fallback" aria-hidden="true">
                              {index + 1}
                            </div>
                          )}
                        </div>
                        <div className="recipes-field">
                          <input
                            type="file"
                            className="recipes-field-input"
                            accept="image/jpeg,image/png,image/webp"
                            onChange={(event) => {
                              const file = event.target.files?.[0] ?? null;
                              setStepFiles((prev) => ({ ...prev, [step.localId]: file }));
                            }}
                            disabled={isStepInteractionDisabled || !step.id}
                          />
                          <div className="recipes-form-actions recipes-form-actions-start">
                            <button
                              type="button"
                              className="btn btn-primary"
                              onClick={() => void uploadStepImage(step.localId)}
                              disabled={isStepInteractionDisabled || !step.id || !stepFiles[step.localId]}
                            >
                              Загрузить фото шага
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={() => void removeStepImage(step.localId)}
                              disabled={isStepInteractionDisabled || !step.image_url || !step.id}
                            >
                              Удалить фото шага
                            </button>
                          </div>
                          {!step.id && (
                            <p className="recipes-field-hint">Фото к новым шагам можно добавить после сохранения рецепта.</p>
                          )}
                        </div>
                      </div>
                    </section>
                  ))}
                </div>
              )}

              <div className="recipes-form-actions">
                <button type="button" className="btn btn-secondary" onClick={addStep} disabled={isStepInteractionDisabled}>
                  Добавить шаг
                </button>
              </div>
            </article>
          </>
        )}
      </div>
    </section>
  );
}
