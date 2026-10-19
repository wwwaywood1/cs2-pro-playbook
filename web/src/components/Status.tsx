export function Loading() {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span />
      <span />
      <span />
    </div>
  );
}

export function ErrorNotice({ error }: { error: Error }) {
  return (
    <div className="notice notice-error" role="alert">
      <strong aria-hidden="true">! </strong>
      <span>{error.message}</span>
    </div>
  );
}
