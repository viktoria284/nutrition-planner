import type { Profile } from "../../api/profiles";
import { CustomSelect } from "../CustomSelect";
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
  const options = [
    { value: "", label: "Выберите профиль" },
    ...profiles.map((profile) => ({ value: String(profile.id), label: formatProfileOptionLabel(profile) })),
  ];

  return (
    <label className="plans-field" htmlFor={id}>
      <span className="plans-field-label-row">
        <span className="plans-field-label">{label}</span>
        {infoText && <InfoPopover text={infoText} ariaLabel={`Подсказка: ${label}`} />}
      </span>
      <CustomSelect
        id={id}
        value={value}
        options={options}
        onChange={onChange}
        disabled={disabled}
        invalid={Boolean(error)}
        ariaLabel={label}
        triggerClassName="plans-field-input"
      />
      {hint && <p className="plans-field-hint">{hint}</p>}
      <div className="plans-field-error-slot" aria-live="polite">
        {error && <p className="plans-field-error">{error}</p>}
      </div>
    </label>
  );
}
