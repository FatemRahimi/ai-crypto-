export function CopilotPanel() {
  return (
    <aside
      className="border-line bg-sheet h-fit rounded-lg border px-5 py-4"
      aria-label="AI copilot"
    >
      <h2 className="font-serif text-xl text-ink">AI Copilot</h2>
      <p className="text-muted mt-3 text-sm leading-relaxed">
        The copilot is not connected. It will not invent market commentary, probabilities, or
        orders.
      </p>
      <label className="mt-5 block text-sm text-ink" htmlFor="copilot-draft">
        Future prompt
      </label>
      <textarea
        id="copilot-draft"
        disabled
        rows={5}
        placeholder="Messages are not sent in Phase 1."
        className="border-line text-muted mt-2 w-full resize-none rounded-md border bg-paper px-3 py-2 text-sm"
      />
      <button
        type="button"
        disabled
        className="border-line text-muted mt-3 w-full cursor-not-allowed rounded-md border px-3 py-2 text-sm"
      >
        Not available
      </button>
    </aside>
  );
}
