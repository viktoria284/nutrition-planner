import { Alert } from "../Alert";

type PlanConfirmModalProps = {
  open: boolean;
  title: string;
  message: string;
  confirmText: string;
  loading: boolean;
  errorText?: string | null;
  onClose: () => void;
  onConfirm: () => void;
};

export function PlanConfirmModal({
  open,
  title,
  message,
  confirmText,
  loading,
  errorText = null,
  onClose,
  onConfirm,
}: PlanConfirmModalProps) {
  if (!open) return null;

  return (
    <div
      className="plans-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (loading) return;
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="plans-modal" role="dialog" aria-modal="true" aria-label={title}>
        <header className="plans-modal-head">
          <h2 className="plans-modal-title">{title}</h2>
          <p className="plans-modal-subtitle">{message}</p>
        </header>

        {errorText && <Alert text={errorText} />}

        <div className="plans-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Отмена
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={loading}>
            {loading ? "Удаляем..." : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
