export function ShowMore({
  shown,
  total,
  onMore,
  label,
  controls,
}: {
  shown: number;
  total: number;
  onMore: () => void;
  label: string;
  controls: string;
}) {
  if (!total) return null;
  return (
    <div className="list-more">
      <span aria-live="polite">
        Показано {Math.min(shown, total)} из {total}
      </span>
      {shown < total && (
        <button
          type="button"
          className="secondary"
          aria-label={label}
          aria-controls={controls}
          onClick={onMore}
        >
          Показать ещё
        </button>
      )}
    </div>
  );
}
