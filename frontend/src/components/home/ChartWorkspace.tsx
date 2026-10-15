export function ChartWorkspace() {
  return (
    <section
      className="border-line bg-sheet rounded-lg border px-5 py-4"
      aria-label="Chart workspace"
    >
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="font-serif text-xl text-ink">Chart workspace</h2>
        <p className="text-muted text-xs tracking-[0.14em] uppercase">No feed</p>
      </div>
      <svg viewBox="0 0 640 240" role="img" className="text-line h-56 w-full">
        <title>Empty chart frame</title>
        <rect x="0" y="0" width="640" height="240" fill="#fbf9f5" />
        {Array.from({ length: 4 }, (_, index) => (
          <line
            key={index}
            x1="24"
            x2="616"
            y1={40 + index * 48}
            y2={40 + index * 48}
            stroke="currentColor"
          />
        ))}
        <text x="320" y="124" textAnchor="middle" fill="#6d665d" fontSize="16">
          No verified series
        </text>
      </svg>
      <p className="text-muted mt-3 text-sm">
        A chart will render here only after a market-data feed is connected. This frame is not a
        price history.
      </p>
    </section>
  );
}
