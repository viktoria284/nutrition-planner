import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import "./CustomSelect.css";

export type CustomSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type CustomSelectProps = {
  id?: string;
  value: string;
  options: CustomSelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  ariaLabel?: string;
  className?: string;
  triggerClassName?: string;
};

type PanelPosition = {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function CustomSelect({
  id,
  value,
  options,
  onChange,
  placeholder = "Выберите",
  disabled = false,
  invalid = false,
  ariaLabel,
  className,
  triggerClassName,
}: CustomSelectProps) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [position, setPosition] = useState<PanelPosition>({ top: 0, left: 0, width: 240, maxHeight: 280 });

  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const selectedOption = useMemo(() => options.find((option) => option.value === value), [options, value]);
  const selectedLabel = selectedOption?.label ?? placeholder;
  const listboxId = id ? `${id}-listbox` : undefined;

  const updatePosition = () => {
    if (!triggerRef.current) return;

    const sidePadding = 12;
    const gap = 6;
    const triggerRect = triggerRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const maxViewportWidth = Math.max(220, viewportWidth - sidePadding * 2);
    const desiredWidth = Math.max(triggerRect.width, Math.min(260, maxViewportWidth));
    const width = Math.min(desiredWidth, maxViewportWidth);
    const left = clamp(triggerRect.left, sidePadding, Math.max(sidePadding, viewportWidth - width - sidePadding));

    const availableBelow = viewportHeight - triggerRect.bottom - gap - sidePadding;
    const availableAbove = triggerRect.top - gap - sidePadding;
    const measuredHeight = panelRef.current?.offsetHeight ?? 240;
    const preferredMaxHeight = Math.min(280, viewportHeight - sidePadding * 2);
    const openAbove = availableBelow < Math.min(measuredHeight, 180) && availableAbove > availableBelow;
    const maxHeight = Math.max(140, Math.min(preferredMaxHeight, openAbove ? availableAbove : availableBelow));
    const top = openAbove
      ? Math.max(sidePadding, triggerRect.top - gap - Math.min(measuredHeight, maxHeight))
      : Math.min(triggerRect.bottom + gap, viewportHeight - sidePadding - Math.min(measuredHeight, maxHeight));

    setPosition({ top, left, width, maxHeight });
    setIsReady(true);
  };

  useEffect(() => {
    if (!open) return undefined;

    const close = () => setOpen(false);
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (rootRef.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onScroll = (event: Event) => {
      const target = event.target as Node | null;
      if (target && panelRef.current?.contains(target)) return;
      close();
    };
    const onTouchMove = (event: TouchEvent) => {
      const target = event.target as Node | null;
      if (target && panelRef.current?.contains(target)) return;
      close();
    };

    window.addEventListener("pointerdown", onPointerDown, true);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", onPointerDown, true);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("touchmove", onTouchMove);
    };
  }, [open]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setOpen(false), 0);
    return () => window.clearTimeout(timeoutId);
  }, [location.pathname, location.search]);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open, options.length, selectedLabel]);

  return (
    <div ref={rootRef} className={`ui-select ${className ?? ""}`.trim()}>
      <button
        id={id}
        ref={triggerRef}
        type="button"
        className={`ui-select-trigger ${triggerClassName ?? ""} ${invalid ? "is-invalid" : ""}`.trim()}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => {
          if (!disabled) {
            setOpen((prev) => {
              if (!prev) setIsReady(false);
              return !prev;
            });
          }
        }}
      >
        <span className={`ui-select-value ${selectedOption ? "" : "is-placeholder"}`.trim()}>{selectedLabel}</span>
        <span className="ui-select-chevron" aria-hidden="true" />
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            id={listboxId}
            className="ui-select-panel"
            role="listbox"
            style={{
              top: `${position.top}px`,
              left: `${position.left}px`,
              width: `${position.width}px`,
              maxHeight: `${position.maxHeight}px`,
              visibility: isReady ? "visible" : "hidden",
            }}
          >
            {options.map((option) => {
              const isSelected = option.value === value;
              return (
                <button
                  key={option.value}
                  type="button"
                  className={`ui-select-option ${isSelected ? "is-selected" : ""}`.trim()}
                  role="option"
                  aria-selected={isSelected}
                  disabled={option.disabled}
                  onClick={() => {
                    if (option.disabled) return;
                    onChange(option.value);
                    setOpen(false);
                    triggerRef.current?.focus();
                  }}
                >
                  {option.label}
                </button>
              );
            })}
          </div>,
          document.body,
        )}
    </div>
  );
}
