type FormErrorSummaryProps = {
  messages: string[];
  className?: string;
  itemClassName?: string;
};

export function FormErrorSummary({
  messages,
  className = "form-error-summary",
  itemClassName = "form-error-summary-item",
}: FormErrorSummaryProps) {
  const hasErrors = messages.length > 0;
  if (!hasErrors) return null;

  return (
    <div className={`${className} is-error`} aria-live="polite">
      {messages.map((message, index) => (
        <p key={`${message}-${index}`} className={itemClassName}>
          {message}
        </p>
      ))}
    </div>
  );
}
