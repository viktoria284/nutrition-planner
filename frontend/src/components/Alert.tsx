export function Alert({ text }: { text: string }) {
  return (
    <div className="alert" role="alert" aria-live="polite">
      <pre>{text}</pre>
    </div>
  );
}
