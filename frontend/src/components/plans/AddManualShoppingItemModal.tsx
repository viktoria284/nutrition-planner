import { useEffect, useState, type FormEvent } from "react";
import { FormErrorSummary } from "../FormErrorSummary";
import type { ShoppingManualItemCreatePayload } from "../../types/shopping";

type AddManualShoppingItemModalProps = {
  open: boolean;
  saving: boolean;
  submitError: string | null;
  onClose: () => void;
  onSubmit: (payload: ShoppingManualItemCreatePayload) => Promise<void>;
};

type ManualFormState = {
  name: string;
  grams: string;
  unit: string;
};

function validatePositiveDecimal(raw: string): { value: string | null; error: string | null } {
  const normalized = raw.trim().replace(",", ".");
  if (!normalized) return { value: null, error: null };
  if (!/^\d+(\.\d+)?$/.test(normalized)) {
    return { value: null, error: "Количество должно быть положительным числом." };
  }
  if (Number(normalized) <= 0) {
    return { value: null, error: "Количество должно быть больше 0." };
  }
  return { value: normalized, error: null };
}

export function AddManualShoppingItemModal({
  open,
  saving,
  submitError,
  onClose,
  onSubmit,
}: AddManualShoppingItemModalProps) {
  const [form, setForm] = useState<ManualFormState>({
    name: "",
    grams: "",
    unit: "",
  });
  const [formErrors, setFormErrors] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    setForm({ name: "", grams: "", unit: "" });
    setFormErrors([]);
  }, [open]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const errors: string[] = [];
    const name = form.name.trim();
    if (!name) errors.push("Введите название позиции.");

    const gramsResult = validatePositiveDecimal(form.grams);
    if (gramsResult.error) errors.push(gramsResult.error);

    const unit = form.unit.trim();
    if (unit.length > 32) errors.push("Единица измерения слишком длинная (до 32 символов).");

    if (errors.length > 0) {
      setFormErrors(errors);
      return;
    }

    setFormErrors([]);
    await onSubmit({
      name,
      ...(gramsResult.value ? { grams: gramsResult.value } : {}),
      ...(unit ? { unit } : {}),
    });
  };

  if (!open) return null;

  return (
    <div
      className="plans-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (saving) return;
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="plans-modal" role="dialog" aria-modal="true" aria-labelledby="manual-item-modal-title">
        <header className="plans-modal-head">
          <h2 id="manual-item-modal-title" className="plans-modal-title">
            Добавить вручную
          </h2>
          <p className="plans-modal-subtitle">Создайте дополнительную позицию, которая не зависит от рецептов.</p>
        </header>

        <form className="plans-modal-form" onSubmit={handleSubmit} noValidate>
          <FormErrorSummary
            messages={[...formErrors, ...(submitError ? [submitError] : [])]}
            className="plans-form-summary form-error-summary"
            itemClassName="plans-form-error-item"
          />

          <label className="plans-field" htmlFor="manual-item-name">
            <span className="plans-field-label">Название</span>
            <input
              id="manual-item-name"
              className="plans-field-input"
              type="text"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              disabled={saving}
              placeholder="Например, Бумажные полотенца"
            />
          </label>

          <label className="plans-field" htmlFor="manual-item-grams">
            <span className="plans-field-label">Количество (опционально)</span>
            <input
              id="manual-item-grams"
              className="plans-field-input"
              type="text"
              inputMode="decimal"
              value={form.grams}
              onChange={(event) => setForm((prev) => ({ ...prev, grams: event.target.value }))}
              disabled={saving}
              placeholder="Например, 250"
            />
          </label>

          <label className="plans-field" htmlFor="manual-item-unit">
            <span className="plans-field-label">Ед. измерения (опционально)</span>
            <input
              id="manual-item-unit"
              className="plans-field-input"
              type="text"
              value={form.unit}
              onChange={(event) => setForm((prev) => ({ ...prev, unit: event.target.value }))}
              disabled={saving}
              placeholder="Например, г, мл, шт"
              maxLength={32}
            />
          </label>

          <div className="plans-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Отмена
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Добавляем..." : "Добавить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
