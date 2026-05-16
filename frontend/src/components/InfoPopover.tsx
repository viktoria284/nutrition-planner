import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./InfoPopover.css";

type InfoPopoverProps = {
  text: string;
  ariaLabel: string;
  className?: string;
};

export function InfoPopover({ text, ariaLabel, className }: InfoPopoverProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0, maxWidth: 320 });
  const [isReady, setIsReady] = useState(false);
  const rootRef = useRef<HTMLSpanElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const updatePosition = () => {
    if (!triggerRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const maxWidth = Math.min(320, Math.max(220, viewportWidth - 24));

    const measuredWidth = panelRef.current?.offsetWidth ?? maxWidth;
    const measuredHeight = panelRef.current?.offsetHeight ?? 140;
    const panelWidth = Math.min(measuredWidth, maxWidth);
    const gap = 8;
    const sidePadding = 12;

    const minLeft = sidePadding;
    const maxLeft = Math.max(minLeft, viewportWidth - panelWidth - sidePadding);
    const centeredLeft = triggerRect.left + (triggerRect.width / 2) - (panelWidth / 2);
    const left = Math.min(Math.max(centeredLeft, minLeft), maxLeft);

    const belowTop = triggerRect.bottom + gap;
    const aboveTop = triggerRect.top - measuredHeight - gap;
    const canOpenAbove = aboveTop >= sidePadding;
    const canOpenBelow = belowTop + measuredHeight <= viewportHeight - sidePadding;

    let top = belowTop;
    if (!canOpenBelow && canOpenAbove) {
      top = aboveTop;
    } else if (!canOpenBelow && !canOpenAbove) {
      top = Math.max(sidePadding, Math.min(belowTop, viewportHeight - measuredHeight - sidePadding));
    }

    setPosition({
      top,
      left,
      maxWidth,
    });
    setIsReady(true);
  };

  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (rootRef.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      setOpen(false);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    setIsReady(false);
    updatePosition();
  }, [open, text]);

  return (
    <span ref={rootRef} className={`info-popover ${className ?? ""}`.trim()}>
      <button
        ref={triggerRef}
        type="button"
        className="info-popover-trigger"
        aria-label={ariaLabel}
        aria-expanded={open}
        onMouseDown={(event) => {
          event.stopPropagation();
        }}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((prev) => !prev);
        }}
      >
        i
      </button>
      {open &&
        createPortal(
          <div
            ref={panelRef}
            className="info-popover-panel"
            style={{
              top: `${position.top}px`,
              left: `${position.left}px`,
              maxWidth: `${position.maxWidth}px`,
              visibility: isReady ? "visible" : "hidden",
            }}
            role="dialog"
            aria-label={ariaLabel}
          >
          {text}
          </div>,
          document.body,
        )}
    </span>
  );
}
