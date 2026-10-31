"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/console/", label: "Console" },
  { href: "/evidence/", label: "Evidence" },
  { href: "/audit/", label: "Audit" },
  { href: "/playground/", label: "Playground" },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href.replace(/\/$/, ""));
}

export function SiteNav() {
  const pathname = usePathname() ?? "/";
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <Link href="/" className="flex items-center gap-2 font-mono text-sm font-semibold">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-gradient-to-br from-ours to-theirs" />
          mergelens
        </Link>
        <nav className="flex gap-1 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={
                "rounded-md px-3 py-1.5 transition-colors " +
                (isActive(pathname, l.href)
                  ? "bg-zinc-800 text-zinc-50"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100")
              }
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-amber-300">
          advisory only
        </span>
      </div>
    </header>
  );
}
