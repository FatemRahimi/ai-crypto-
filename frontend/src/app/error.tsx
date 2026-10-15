"use client";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  void error;
  return (
    <div className="max-w-xl">
      <h1 className="font-serif text-3xl text-ink">This page could not be shown</h1>
      <p className="text-muted mt-3 text-sm leading-relaxed">
        The application hit an unexpected error. Nothing was sent to an exchange.
      </p>
      <button
        type="button"
        onClick={reset}
        className="border-moss text-moss mt-6 rounded-md border px-4 py-2 text-sm"
      >
        Try again
      </button>
    </div>
  );
}
