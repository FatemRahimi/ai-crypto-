"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/content/navigation";

export function SideNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="border-line border-b px-4 py-6 lg:border-r lg:border-b-0 lg:px-5"
    >
      <Link href="/" className="block px-3">
        <span className="font-serif text-2xl text-ink">AI-Crypto</span>
        <span className="mt-1 block text-xs tracking-[0.16em] text-muted uppercase">
          Phase 1 foundation
        </span>
      </Link>
      <ul className="mt-8 flex gap-1 overflow-x-auto lg:flex-col">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`block rounded-md px-3 py-2 text-sm ${
                  active ? "bg-moss-soft text-moss" : "text-ink hover:bg-sand"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
