import { MARKET_STATES } from "@/content/navigation";

export function StatusVocabulary({ sample }: { sample?: (typeof MARKET_STATES)[number] }) {
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Possible states">
      {MARKET_STATES.map((state) => {
        const selected = sample === state;
        return (
          <li
            key={state}
            className={`rounded-sm border px-2 py-1 text-xs tracking-[0.08em] ${
              selected ? "border-demo text-demo" : "border-line text-muted"
            }`}
          >
            {state}
            {selected ? " · sample" : ""}
          </li>
        );
      })}
    </ul>
  );
}
