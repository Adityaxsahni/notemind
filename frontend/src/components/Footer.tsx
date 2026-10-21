import Link from "next/link";

import { REPO_URL, SITE_NAME } from "@/lib/site";

import { Logo } from "./icons";
import { CookieSettingsButton } from "./SiteChrome";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { href: "/features", label: "Features" },
      { href: "/signup", label: "Create an account" },
      { href: "/login", label: "Log in" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/privacy", label: "Privacy policy" },
      { href: "/terms", label: "Terms and conditions" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-24 border-t border-border">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div className="max-w-sm">
          <Link href="/" className="flex items-center gap-2">
            <Logo />
            <span className="display text-2xl">{SITE_NAME}</span>
          </Link>
          <p className="mt-3 text-sm text-ink-soft">
            Answers from your own course notes, with a page citation for every claim. Private by
            default.
          </p>
        </div>
        {COLUMNS.map((column) => (
          <div key={column.title}>
            <h2 className="label-mono">{column.title}</h2>
            <ul className="mt-3 space-y-2 text-sm">
              {column.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="text-ink-soft hover:text-accent">
                    {l.label}
                  </Link>
                </li>
              ))}
              {column.title === "Legal" && (
                <li>
                  <CookieSettingsButton className="text-ink-soft hover:text-accent" />
                </li>
              )}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-5 text-xs text-muted sm:flex-row sm:justify-between sm:px-6">
          <p className="font-mono">© 2026 {SITE_NAME} · a student project</p>
          <p>
            Know a course we should support next?{" "}
            <a href={REPO_URL} className="font-semibold text-accent hover:underline" rel="noopener noreferrer" target="_blank">
              Tell us on GitHub →
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
