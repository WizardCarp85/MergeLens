import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteNav } from "@/components/site-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "mergelens", template: "%s · mergelens" },
  description: "Git-native merge conflict advisor. Advisory only — Git stays the source of truth.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <SiteNav />
        <main className="mx-auto w-full max-w-6xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 pb-10 text-xs text-zinc-500">
          mergelens is advisory — the dashboard never edits files or commits. Decisions are saved
          as <em>pending</em>; finish from the terminal with{" "}
          <code className="rounded bg-zinc-900 px-1 py-0.5 font-mono">mergelens commit</code>.
        </footer>
      </body>
    </html>
  );
}
