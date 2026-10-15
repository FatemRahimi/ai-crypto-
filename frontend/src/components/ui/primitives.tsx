import type { ReactNode } from "react";

export function DemoMark() {
  return (
    <span className="border-demo/40 text-demo rounded-sm border px-1.5 py-0.5 text-[10px] tracking-[0.14em] uppercase">
      Demo
    </span>
  );
}

export function PlannedTag() {
  return (
    <span className="border-line text-muted rounded-sm border px-1.5 py-0.5 text-[10px] tracking-[0.14em] uppercase">
      Planned
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  summary,
}: {
  eyebrow: string;
  title: string;
  summary: string;
}) {
  return (
    <header className="mb-8 max-w-3xl">
      <p className="text-muted text-xs tracking-[0.16em] uppercase">{eyebrow}</p>
      <h1 className="mt-2 font-serif text-4xl text-ink">{title}</h1>
      <p className="text-muted mt-3 text-base leading-relaxed">{summary}</p>
    </header>
  );
}

export function Panel({
  title,
  demo = false,
  aside,
  children,
}: {
  title: string;
  demo?: boolean;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      className={`bg-sheet rounded-lg border px-5 py-4 ${demo ? "border-demo/50 border-dashed" : "border-line"}`}
      data-demo={demo ? "true" : undefined}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <h2 className="font-serif text-xl text-ink">{title}</h2>
        {demo ? <DemoMark /> : aside}
      </div>
      {children}
    </section>
  );
}

export function FieldList({ fields }: { fields: readonly string[] }) {
  return (
    <dl className="divide-line divide-y">
      {fields.map((field) => (
        <div key={field} className="flex items-baseline justify-between gap-4 py-2">
          <dt className="text-muted text-sm">{field}</dt>
          <dd className="text-sm text-ink">—</dd>
        </div>
      ))}
    </dl>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="text-muted text-sm leading-relaxed">{children}</p>;
}
