import { useEffect } from "react";

type LogoutConfirmModalProps = {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function LogoutConfirmModal({ open, onCancel, onConfirm }: LogoutConfirmModalProps) {
  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="app-confirm-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="app-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="logout-confirm-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="logout-confirm-title" className="app-confirm-title">
          Выйти из аккаунта?
        </h2>
        <p className="app-confirm-text">Для продолжения работы потребуется снова войти.</p>

        <div className="app-confirm-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            Остаться
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm}>
            Выйти
          </button>
        </div>
      </div>
    </div>
  );
}
