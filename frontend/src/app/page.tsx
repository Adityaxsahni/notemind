import type { Metadata } from "next";
import Link from "next/link";

import { ArrowRightIcon } from "@/components/icons";
import { Chip, Eyebrow, HatchTile } from "@/components/ui";
import { SITE_DESCRIPTION } from "@/lib/site";

export const metadata: Metadata = {
  title: { absolute: "NoteMind: answers from your own notes, with page citations" },
  description: SITE_DESCRIPTION,
  alternates: { canonical: "/" },
};

const FACTS = [
  { label: "Source", value: "Lecture 7, page 12" },
  { label: "First words in", value: "~1.5 seconds" },
  { label: "Read from", value: "Handwritten notes" },
  { label: "Right now", value: "Grounded", dot: true },
];

const STEPS = [
  {
    title: "Upload your notes",
    meta: "pdf · slides · word · photos · up to 200 mb",
    text: "Course packs, lecture slides with speaker notes, and photos or scans of handwritten pages.",
  },
  {
    title: "Ask anything",
    meta: "answers stream in · every claim cited",
    text: "Plain-English questions, answered only from your material, with the page each claim came from.",
  },
  {
    title: "Quiz yourself",
    meta: "exam-style · explanations · source page",
    text: "Multiple-choice questions written from your own notes, on one topic or the whole course.",
  },
];

const PROMISES = [
  ["Every claim cited", "Click a citation to open the page. Check, don't trust."],
  ["Honest when it doesn't know", "If your notes don't cover it, NoteMind says so instead of guessing."],
  ["Private by default", "Your courses are visible only to you, enforced down to the database."],
  ["Revise with classmates", "Share a course read-only with a link you can revoke any time."],
];

export default function LandingPage() {
  return (
    <>
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-14 sm:px-6 sm:pt-20 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <Eyebrow className="animate-rise">NoteMind · study assistant</Eyebrow>
          <h1 className="display animate-rise mt-4 text-6xl [animation-delay:60ms] sm:text-7xl lg:text-8xl">
            Your notes.
            <br />
            Your <em>answers</em>.
          </h1>
          <p className="animate-rise mt-6 max-w-lg text-base leading-relaxed text-ink-soft [animation-delay:120ms] sm:text-lg">
            Upload your lecture notes, slides and handwritten pages, then ask questions in plain English.
            NoteMind answers only from what your course teaches, and cites the page for every claim.
          </p>
          <div className="animate-rise mt-8 flex flex-wrap items-center gap-3 [animation-delay:180ms]">
            <Link
              href="/signup"
              className="group inline-flex items-center gap-2 rounded-full bg-foreground px-7 py-3.5 text-base font-medium text-background transition hover:bg-foreground/85"
            >
              Get started free
              <ArrowRightIcon className="size-5 transition group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/features"
              className="inline-flex items-center rounded-full border border-foreground/25 px-6 py-3.5 text-base transition hover:border-foreground"
            >
              See how it works
            </Link>
          </div>
          <p className="meta mt-5">no credit card · delete your account and data any time</p>
        </div>

        {/* The course picker, as on the app's first screen. */}
        <div className="animate-rise mx-auto w-full max-w-sm [animation-delay:240ms]">
          <div className="overflow-hidden rounded-2xl border-[1.5px] border-foreground bg-surface shadow-card-lg">
            <HatchTile caption="lecture 7 · krebs cycle, handwritten" className="h-40" />
            <div className="flex items-end justify-between gap-3 p-4">
              <div>
                <p className="display text-3xl">Cell Biology</p>
                <p className="meta mt-1">412 pages · 1,180 passages</p>
              </div>
              <span className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground">
                Enter
              </span>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {[
              ["Organic Chem", "indexing"],
              ["Physics II", "queued"],
            ].map(([name, state]) => (
              <div key={name} className="rounded-2xl border border-dashed border-faint p-3.5">
                <p className="display text-xl text-muted">{name}</p>
                <p className="label-mono mt-1">{state}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* An answer, laid out like a place's detail screen. */}
      <section aria-labelledby="answer" className="reveal mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid overflow-hidden rounded-3xl border border-border bg-surface lg:grid-cols-2">
          <HatchTile caption="your notes, page 12" className="min-h-56 lg:min-h-full">
            <span className="absolute right-4 top-4 rounded-full bg-background px-4 py-1.5 text-sm font-medium">
              Saved
            </span>
            <Chip tone="accent" className="absolute left-4 top-4">
              picked from your notes
            </Chip>
          </HatchTile>
          <div className="p-6 sm:p-8">
            <Eyebrow>Biology 101</Eyebrow>
            <h2 id="answer" className="display mt-2 text-4xl sm:text-5xl">
              How do mitochondria make ATP?
            </h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <Chip tone="tag">from your notes</Chip>
              <Chip tone="tag">two sources</Chip>
              <Chip tone="tag">exam favourite</Chip>
            </div>
            <dl className="mt-6 grid grid-cols-2 overflow-hidden rounded-2xl border border-border">
              {FACTS.map(({ label, value, dot }, i) => (
                <div
                  key={label}
                  className={`p-3.5 ${i % 2 ? "border-l border-border" : ""} ${i > 1 ? "border-t border-border" : ""} ${dot ? "bg-surface-2" : ""}`}
                >
                  <dt className="label-mono">{label}</dt>
                  <dd className="mt-1 flex items-center gap-1.5 text-sm font-semibold">
                    {dot && <span aria-hidden className="size-1.5 rounded-full bg-amber" />}
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="label-mono mt-6">What your notes said</p>
            <blockquote className="mt-2 flex gap-3">
              <span aria-hidden className="mt-1 size-7 shrink-0 rounded-full bg-chip" />
              <div>
                <p className="text-sm leading-relaxed text-ink-soft">
                  &ldquo;The electron transport chain pumps protons across the inner membrane; ATP synthase
                  uses that gradient to make ATP.&rdquo;
                </p>
                <p className="meta mt-1">lecture 7 · page 12 · handwritten</p>
              </div>
            </blockquote>
            <div className="mt-6 flex items-center gap-3">
              <Link
                href="/signup"
                className="flex-1 rounded-full bg-foreground py-3.5 text-center text-sm font-medium text-background transition hover:bg-foreground/85"
              >
                Ask your own notes
              </Link>
              <Link
                href="/features"
                aria-label="See all features"
                className="grid size-12 place-items-center rounded-full border border-foreground/40 transition hover:border-foreground"
              >
                <ArrowRightIcon className="size-5 -rotate-45" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="how" className="reveal mx-auto mt-24 max-w-6xl px-4 sm:px-6">
        <Eyebrow>How it works</Eyebrow>
        <h2 id="how" className="display mt-2 text-5xl">
          Three steps, <em>no</em> setup.
        </h2>
        <ol className="mt-8 grid gap-3">
          {STEPS.map(({ title, meta, text }, i) => (
            <li
              key={title}
              className={`card-lift flex flex-col gap-4 rounded-2xl border bg-surface p-4 sm:flex-row sm:items-center ${
                i === 0 ? "border-[1.5px] border-foreground" : "border-border"
              }`}
            >
              <div className="flex gap-1.5">
                {[0, 1, 2].map((k) => (
                  <HatchTile key={k} className="size-11 rounded-lg" />
                ))}
              </div>
              <div className="flex-1">
                <h3 className="display text-2xl">{title}</h3>
                <p className="meta">{meta}</p>
                <p className="mt-1 text-sm text-ink-soft">{text}</p>
              </div>
              <span className="font-mono text-sm text-accent">0{i + 1}</span>
            </li>
          ))}
        </ol>
      </section>

      {/* Handwriting, drawn like the map screen: grid paper, a pin, a dark tooltip. */}
      <section aria-labelledby="handwriting" className="reveal mx-auto mt-24 max-w-6xl px-4 sm:px-6">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <Eyebrow>New · handwriting</Eyebrow>
            <h2 id="handwriting" className="display mt-2 text-5xl">
              Photos of the whiteboard <em>count</em> too.
            </h2>
            <p className="mt-4 max-w-md leading-relaxed text-ink-soft">
              Upload scanned or handwritten PDFs, or snap a photo of your notebook. NoteMind reads the
              handwriting, keeps the page numbers, and cites it like any typed page.
            </p>
            <p className="meta mt-4">jpg · png · webp · scanned pdf · up to 300 handwritten pages per file</p>
          </div>
          <div className="grid-paper relative h-72 overflow-hidden rounded-3xl border border-border">
            <div aria-hidden className="absolute -left-10 top-24 h-6 w-[130%] -rotate-6 bg-[#d8cfb8]" />
            <div aria-hidden className="absolute -left-10 top-52 h-5 w-[130%] rotate-3 bg-[#d8cfb8]" />
            <div className="absolute right-6 top-6 grid h-24 w-36 place-items-center rounded-2xl bg-sage">
              <span className="display text-xl italic text-ink-soft">Krebs cycle</span>
            </div>
            <div className="absolute left-[18%] top-[28%] rounded-xl bg-foreground px-3 py-2 text-background shadow-card-lg">
              <p className="text-sm font-semibold">Page 3, transcribed</p>
              <p className="font-mono text-[0.625rem] text-background/70">handwritten · 412 words</p>
            </div>
            <span aria-hidden className="pin absolute left-[30%] top-[52%] size-2.5 rounded-full bg-accent" />
            <div className="absolute inset-x-4 bottom-4 rounded-2xl bg-background p-3.5 shadow-card">
              <p className="label-mono text-accent">from your photo</p>
              <p className="mt-1 text-sm font-medium">Acetyl-CoA → citrate → … → oxaloacetate</p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="why" className="reveal mx-auto mt-24 max-w-6xl px-4 sm:px-6">
        <Eyebrow>Why NoteMind</Eyebrow>
        <h2 id="why" className="display mt-2 text-5xl">
          Answers you can <em>trust</em>.
        </h2>
        <ul className="mt-8 grid gap-3 sm:grid-cols-2">
          {PROMISES.map(([title, text]) => (
            <li key={title} className="rounded-2xl border border-border bg-surface p-5">
              <h3 className="display text-2xl">{title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ink-soft">{text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="reveal mx-auto mt-24 max-w-6xl px-4 sm:px-6">
        <div className="rounded-3xl bg-foreground px-6 py-14 text-center text-background sm:px-12">
          <p className="eyebrow !text-[#f0a48f]">Exam season</p>
          <h2 className="display mt-3 text-5xl sm:text-6xl">
            Ready for your <em>next</em> exam?
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-background/80">
            Create a free account, upload one course, and ask your first question in under a minute.
          </p>
          <Link
            href="/signup"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-accent px-8 py-3.5 font-medium text-accent-foreground transition hover:bg-accent/90"
          >
            Create your free account
            <ArrowRightIcon className="size-5" />
          </Link>
        </div>
      </section>
    </>
  );
}
