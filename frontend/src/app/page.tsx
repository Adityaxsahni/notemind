import type { Metadata } from "next";
import Link from "next/link";

import {
  ArrowRightIcon,
  BookIcon,
  CameraIcon,
  CiteIcon,
  DocumentIcon,
  PenIcon,
  SearchOffIcon,
  SigmaIcon,
  SlidesIcon,
} from "@/components/icons";
import { Chip, Eyebrow, HatchTile } from "@/components/ui";
import { SITE_DESCRIPTION } from "@/lib/site";

export const metadata: Metadata = {
  title: { absolute: "NoteMind: answers from your own notes, with page citations" },
  description: SITE_DESCRIPTION,
  alternates: { canonical: "/" },
};

const FORMATS = [
  { icon: DocumentIcon, name: "PDF", meta: "up to 200 mb" },
  { icon: SlidesIcon, name: "Slides", meta: "speaker notes too" },
  { icon: CameraIcon, name: "Photos", meta: "handwriting read" },
  { icon: SigmaIcon, name: "Math", meta: "kept as formulas" },
];

const FACTS = [
  { label: "Every claim", value: "Cited to its page" },
  { label: "First words in", value: "About 2 seconds" },
  { label: "Reads", value: "Typed, handwritten, math" },
  { label: "Right now", value: "Grounded in your notes", dot: true },
];

const ANSWER_TRAITS = [
  { icon: CiteIcon, title: "Cited", text: "Every statement links to the page it came from." },
  { icon: SigmaIcon, title: "Exact math", text: "Formulas appear properly typeset, not as garbled text." },
  { icon: SearchOffIcon, title: "Honest", text: "If your notes don't cover it, NoteMind says so." },
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

        {/* One library for every kind of note. */}
        <div className="animate-rise mx-auto w-full max-w-sm [animation-delay:240ms]">
          <div className="overflow-hidden rounded-2xl border-[1.5px] border-foreground bg-surface shadow-card-lg">
            <HatchTile caption="your notes, in one place" className="grid h-40 place-items-center">
              <span className="grid size-20 place-items-center rounded-full bg-background text-foreground shadow-card">
                <BookIcon className="size-9" />
              </span>
            </HatchTile>
            <div className="flex items-end justify-between gap-3 p-4">
              <div>
                <p className="display text-3xl">Your library</p>
                <p className="meta mt-1">one course per collection</p>
              </div>
              <span className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground">
                Upload
              </span>
            </div>
          </div>
          <ul className="mt-3 grid grid-cols-2 gap-3">
            {FORMATS.map(({ icon: Icon, name, meta }) => (
              <li key={name} className="flex items-center gap-3 rounded-2xl border border-dashed border-faint p-3.5">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-chip text-foreground">
                  <Icon className="size-[18px]" />
                </span>
                <div className="min-w-0">
                  <p className="display text-xl leading-none">{name}</p>
                  <p className="label-mono mt-1">{meta}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* What an answer gives you, laid out like a detail screen. */}
      <section aria-labelledby="answer" className="reveal mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid overflow-hidden rounded-3xl border border-border bg-surface lg:grid-cols-2">
          <HatchTile caption="every answer, checked against your pages" className="grid min-h-56 place-items-center lg:min-h-full">
            <span className="absolute right-4 top-4 rounded-full bg-background px-4 py-1.5 text-sm font-medium">
              Cited
            </span>
            <Chip tone="accent" className="absolute left-4 top-4">
              from your notes only
            </Chip>
            <div className="flex gap-3">
              {ANSWER_TRAITS.map(({ icon: Icon, title }) => (
                <span
                  key={title}
                  className="grid size-16 place-items-center rounded-2xl bg-background text-foreground shadow-card sm:size-20"
                >
                  <Icon className="size-8" />
                </span>
              ))}
            </div>
          </HatchTile>
          <div className="p-6 sm:p-8">
            <Eyebrow>Every answer</Eyebrow>
            <h2 id="answer" className="display mt-2 text-4xl sm:text-5xl">
              Clear, cited, and <em>exact</em>.
            </h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <Chip tone="tag">steps and key terms</Chip>
              <Chip tone="tag">formulas typeset</Chip>
              <Chip tone="tag">page citations</Chip>
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
            <ul className="mt-6 space-y-3">
              {ANSWER_TRAITS.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-chip text-foreground">
                    <Icon className="size-4" />
                  </span>
                  <p className="text-sm leading-relaxed text-ink-soft">
                    <span className="font-semibold text-foreground">{title}.</span> {text}
                  </p>
                </li>
              ))}
            </ul>
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

      {/* Handwriting: photo in, searchable text out. */}
      <section aria-labelledby="handwriting" className="reveal mx-auto mt-24 max-w-6xl px-4 sm:px-6">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <Eyebrow>Handwriting and math</Eyebrow>
            <h2 id="handwriting" className="display mt-2 text-5xl">
              Photos of the whiteboard <em>count</em> too.
            </h2>
            <p className="mt-4 max-w-md leading-relaxed text-ink-soft">
              Upload scanned or handwritten PDFs, or snap a photo of your notebook. NoteMind reads the
              handwriting and the equations, keeps the page numbers, and cites them like any typed page.
            </p>
            <p className="meta mt-4">jpg · png · webp · scanned pdf · up to 300 handwritten pages per file</p>
          </div>
          <div className="grid-paper relative overflow-hidden rounded-3xl border border-border p-6 sm:p-8">
            <ol className="flex items-center justify-between gap-2">
              {[
                { icon: CameraIcon, label: "Photo or scan" },
                { icon: PenIcon, label: "Handwriting read" },
                { icon: DocumentIcon, label: "Searchable page" },
              ].map(({ icon: Icon, label }, i) => (
                <li key={label} className="flex flex-1 items-center gap-2">
                  <div className="flex flex-1 flex-col items-center gap-2 text-center">
                    <span
                      className={`grid size-16 place-items-center rounded-2xl shadow-card ${
                        i === 1 ? "bg-foreground text-background" : "bg-background text-foreground"
                      }`}
                    >
                      <Icon className="size-7" />
                    </span>
                    <span className="label-mono !text-foreground">{label}</span>
                  </div>
                  {i < 2 && <ArrowRightIcon aria-hidden className="size-5 shrink-0 text-muted" />}
                </li>
              ))}
            </ol>
            <div className="mt-6 rounded-2xl bg-background p-4 shadow-card">
              <div className="flex items-center gap-2">
                <span aria-hidden className="pin size-2 rounded-full bg-accent" />
                <p className="label-mono !text-accent">Ready to search</p>
              </div>
              <div aria-hidden className="mt-3 space-y-2">
                <div className="h-2 w-11/12 rounded-full bg-chip" />
                <div className="h-2 w-9/12 rounded-full bg-chip" />
                <div className="flex items-center gap-2">
                  <SigmaIcon className="size-4 text-muted" />
                  <div className="h-2 w-6/12 rounded-full bg-chip" />
                </div>
              </div>
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
