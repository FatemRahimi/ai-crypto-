import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-xl">
      <h1 className="font-serif text-3xl text-ink">Page not found</h1>
      <p className="text-muted mt-3 text-sm">That address is not part of this application.</p>
      <Link href="/" className="text-moss mt-6 inline-block text-sm">
        Return home
      </Link>
    </div>
  );
}
