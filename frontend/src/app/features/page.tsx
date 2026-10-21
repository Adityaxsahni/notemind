import type { Metadata } from "next";
import Link from "next/link";

import { ArrowRightIcon, AskScene, QuizScene, ShareScene, UploadScene } from "@/components/icons";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Ask questions about your own notes with page citations, generate quizzes, share courses with classmates, and upload PDFs, slides and Word files.",
  alternates: { canonical: "/features" },
};

const SERVICES = [
  {
    scene: AskScene,
    title: "Ask your notes",
    text: "Plain-English questions, answered from your material with a citation for every claim.",
    href: "/signup",
  },
  {
    scene: QuizScene,
    title: "Quiz yourself",
    text: "Exam-style multiple-choice questions with explanations, on a topic or the whole course.",
    href: "/signup",
  },
  {
    scene: ShareScene,
    title: "Study together",
    text: "Share a course read-only with classmates through a link you can revoke at any time.",
    href: "/signup",
  },
  {
    scene: UploadScene,
    title: "Bring any format",
    text: "PDF, PowerPoint with speaker notes, Word, and photos or scans of handwritten notes, up to 200 MB per file.",
    href: "/signup",
  },
];

const FAQ = [
  {
    q: "Does NoteMind make things up?",
    a: "It answers only from passages retrieved from your notes and must cite them. When nothing relevant is found it says \"I couldn't find this in your notes\" instead of answering. Citations let you check every claim.",
  },
  {
    q: "Who can see my notes?",
    a: "Only you, unless you share a course. Access is checked in the application and enforced again by the database itself, so a bug in one layer can't expose your files.",
  },
  {
    q: "What happens to my data if I leave?",
    a: "Export everything as a file from your account page, or delete your account: your files, notes and course data are removed at once.",
  },
  {
    q: "Can it read my handwriting?",
    a: "Yes. Upload a scanned or handwritten PDF, or a photo of your notebook (JPG, PNG or WebP). Pages without typed text are transcribed by the AI model, then searched and cited like any other page. Words it can't make out are marked [illegible] rather than guessed.",
  },
  {
    q: "Can I use it during exams?",
    a: "No. NoteMind is for revision. Using it in an exam would break the terms and almost certainly your college's rules.",
  },
];

export default function FeaturesPage() {
  return (
    <div>
      <div className="mx-auto max-w-6xl px-4 pb-8 pt-16 sm:px-6">
        <header className="animate-rise max-w-2xl">
          <p className="eyebrow">Features</p>
          <h1 className="display mt-3 text-6xl sm:text-7xl">
            Everything you need to <em>revise</em>.
          </h1>
          <p className="mt-4 text-lg text-ink-soft">Learn from your own material, not the whole internet.</p>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="rounded-full bg-foreground px-3.5 py-1.5 text-xs text-background">exam season</span>
            <span className="rounded-full border border-foreground/20 px-3.5 py-1.5 text-xs text-ink-soft">study grind</span>
            <span className="rounded-full border border-foreground/20 px-3.5 py-1.5 text-xs text-ink-soft">group revision</span>
          </div>
        </header>

        <ul className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {SERVICES.map(({ scene: Scene, title, text, href }) => (
            <li key={title} className="reveal">
              <Link
                href={href}
                className="card-lift group flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface"
              >
                <div className="p-3">
                  <Scene />
                </div>
                <div className="flex flex-1 flex-col px-5 pb-5">
                  <h2 className="display text-3xl">{title}</h2>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-ink-soft">{text}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">
                    Try it free <ArrowRightIcon className="size-4 transition group-hover:translate-x-1" />
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>

        <section aria-labelledby="faq" className="reveal mx-auto mt-24 max-w-3xl">
          <p className="eyebrow">What people ask</p>
          <h2 id="faq" className="display mt-2 text-5xl">
            Questions, <em>answered</em>.
          </h2>
          <div className="mt-8 divide-y divide-border rounded-2xl border border-border bg-surface">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group px-5 py-4 [&_summary::-webkit-details-marker]:hidden">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  {q}
                  <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full border border-foreground/25 font-mono transition group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-ink-soft">{a}</p>
              </details>
            ))}
          </div>
        </section>

        <div className="mt-16 text-center">
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 rounded-full bg-foreground px-8 py-3.5 font-medium text-background hover:bg-foreground/85"
          >
            Get started free <ArrowRightIcon className="size-5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
