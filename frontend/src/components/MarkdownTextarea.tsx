import { useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownTextareaProps = {
  id: string;
  label?: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  disabled?: boolean;
  rows?: number;
  showPreview?: boolean;
  compact?: boolean;
  textareaClassName?: string;
};

function wrapSelection(text: string, start: number, end: number, before: string, after: string) {
  const selected = text.slice(start, end) || "текст";
  return `${text.slice(0, start)}${before}${selected}${after}${text.slice(end)}`;
}

function prependList(text: string, start: number, end: number, ordered: boolean) {
  const selected = text.slice(start, end) || "пункт";
  const lines = selected.split("\n");
  const next = lines
    .map((line, index) => {
      const normalized = line.trim() || "пункт";
      return ordered ? `${index + 1}. ${normalized}` : `- ${normalized}`;
    })
    .join("\n");
  return `${text.slice(0, start)}${next}${text.slice(end)}`;
}

export function MarkdownTextarea({
  id,
  label,
  value,
  onChange,
  placeholder,
  disabled = false,
  rows = 5,
  showPreview = true,
  compact = false,
  textareaClassName,
}: MarkdownTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const hasPreview = useMemo(() => showPreview && value.trim().length > 0, [showPreview, value]);

  const apply = (builder: (text: string, start: number, end: number) => string) => {
    const element = textareaRef.current;
    if (!element) return;
    const start = element.selectionStart;
    const end = element.selectionEnd;
    const next = builder(value, start, end);
    onChange(next);
    requestAnimationFrame(() => {
      element.focus();
      element.setSelectionRange(start, end);
    });
  };

  return (
    <div className="markdown-textarea">
      {label && <span className="recipes-field-label">{label}</span>}
      <div className="markdown-toolbar">
        <button type="button" className="btn btn-secondary" onClick={() => apply((text, start, end) => wrapSelection(text, start, end, "**", "**"))} disabled={disabled}>
          Ж
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => apply((text, start, end) => wrapSelection(text, start, end, "*", "*"))} disabled={disabled}>
          К
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => apply((text, start, end) => prependList(text, start, end, false))} disabled={disabled}>
          Список
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => apply((text, start, end) => prependList(text, start, end, true))} disabled={disabled}>
          Нумерованный список
        </button>
      </div>
      <textarea
        ref={textareaRef}
        id={id}
        className={`recipes-field-textarea ${compact ? "recipes-field-textarea--compact" : ""} ${textareaClassName ?? ""}`.trim()}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
      />
      {hasPreview && (
        <details className="markdown-preview-card">
          <summary className="markdown-preview-summary">Предпросмотр</summary>
          <div className="markdown-preview-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
          </div>
        </details>
      )}
    </div>
  );
}

export function MarkdownContent({ value }: { value: string }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
    </div>
  );
}
