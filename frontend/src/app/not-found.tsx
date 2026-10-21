import type { Metadata } from "next";
import Link from "next/link";


export const metadata: Metadata = { title: "Page not found", robots: { index: false } };

export default function NotFound() {
  return (
    <div>
      <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-20 text-center">
        <div aria-hidden className="hatch relative h-36 w-full max-w-sm overflow-hidden rounded-2xl">
          <span className="tile-caption absolute bottom-2 left-2">page 404 · not found</span>
        </div>
        <p className="eyebrow mt-8">Error 404</p>
        <h1 className="display mt-2 text-5xl sm:text-6xl">
          This page isn&apos;t in <em>our notes</em>.
        </h1>
        <p className="mt-4 text-ink-soft">
          The link may be old or mistyped. If it was a course link, the course may have been deleted
          or not shared with you.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link href="/" className="rounded-full bg-foreground px-6 py-3 font-medium text-background hover:bg-foreground/85">
            Go to the home page
          </Link>
          <Link href="/courses" className="rounded-full border border-foreground/25 px-6 py-3 font-medium hover:border-foreground">
            Your courses
          </Link>
        </div>
      </div>
    </div>
  );
}
