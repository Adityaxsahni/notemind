import type { ReactNode } from "react";

import { LEGAL_UPDATED } from "@/lib/site";

export function LegalPage({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
      <header className="border-b border-border pb-6">
        <p className="eyebrow">Legal</p>
        <h1 className="display mt-2 text-5xl sm:text-6xl">{title}</h1>
        <p className="mt-3 text-ink-soft">{intro}</p>
        <p className="meta mt-2">last updated · {LEGAL_UPDATED}</p>
      </header>
      <div className="legal">{children}</div>
    </article>
  );
}
