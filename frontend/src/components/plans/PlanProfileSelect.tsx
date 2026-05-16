import type { Profile } from "../../api/profiles";
import { InfoPopover } from "../InfoPopover";
import { formatProfileOptionLabel } from "./planProfileOptions";

type PlanProfileSelectProps = {
  id: string;
  profiles: Profile[];
  value: string;
  onChange: (value: string) => void;
  label?: string;
  error?: string;
  disabled?: boolean;
  hint?: string;
  infoText?: string;
};

export function PlanProfileSelect({
  id,
  profiles,
  value,
  onChange,
  label = "Профиль питания",
  error,
  disabled = false,
  hint,
  infoText,
}: PlanProfileSelectProps) {
  return (
    <label className="plans-field" htmlFor={id}>
      <span className="plans-field-label-row">
        <span className="plans-field-label">{label}</span>
        {infoText && <InfoPopover text={infoText} ariaLabel={`Подсказка: ${label}`} />}
      </span>
      <select
        id={id}
        className={`plans-field-input ${error ? "is-invalid" : ""}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        <option value="">Выберите профиль</option>
        {profiles.map((profile) => (
          <option key={profile.id} value={String(profile.id)}>
            {formatProfileOptionLabel(profile)}
          </option>
        ))}
      </select>
      {hint && <p className="plans-field-hint">{hint}</p>}
      <div className="plans-field-error-slot" aria-live="polite">
        {error && <p className="plans-field-error">{error}</p>}
      </div>
    </label>
  );
}
