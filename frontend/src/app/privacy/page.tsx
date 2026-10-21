import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/LegalPage";
import { CONTACT_EMAIL, SITE_NAME } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: `What ${SITE_NAME} collects, why, who it is shared with, how long it is kept, and your rights.`,
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      intro={`${SITE_NAME} is a study assistant for your own course notes. This page explains, in plain language, what data we hold and why.`}
    >
      <h2 id="summary">The short version</h2>
      <ul>
        <li>We collect only what the service needs: your email, a hashed password, and the files you upload.</li>
        <li>Your courses are private to you unless you share them.</li>
        <li>When you ask a question, the relevant excerpts of your notes are sent to an AI model provider to write the answer.</li>
        <li>
          When you upload a photo, or a PDF page that has no typed text (handwriting, scans), an image of that page is
          sent to the AI model provider to transcribe it.
        </li>
        <li>No advertising, no selling of data, no third-party trackers.</li>
        <li>You can export everything or delete your account at any time, from your account page.</li>
      </ul>

      <h2 id="data">What we collect</h2>
      <h3>Account</h3>
      <p>Your email address and a password hash (Argon2id; we never store or see your actual password).</p>
      <h3>Your study material</h3>
      <p>
        Files you upload (PDF, PowerPoint, Word), the text extracted from them, and numerical
        representations of that text (&ldquo;embeddings&rdquo;) used for search. Course names, sharing
        links and the list of classmates you share with.
      </p>
      <h3>Questions and answers</h3>
      <p>
        Questions are processed to produce an answer and are not stored with your account. To answer
        a repeated question quickly, an answer may be cached for up to 24 hours, keyed to the course
        rather than to you.
      </p>
      <h3>Security and operations</h3>
      <p>
        Server logs record technical events (for example &ldquo;request failed&rdquo; or token counts)
        but never the contents of your notes, questions or answers. For abuse prevention we keep
        short-lived counters per IP address (minutes to a day), and an audit log of security-relevant
        actions such as account deletion or changes to sharing. Audit entries store a one-way keyed
        hash of the IP address, not the address itself.
      </p>
      <h3>Anonymous analytics (only with your consent)</h3>
      <p>
        If you accept analytics, we count page views: which page, the referring website&rsquo;s
        domain, and whether the device is mobile or desktop. No cookies, user ids or IP addresses
        are stored, ids in addresses are removed, and Do Not Track and Global Privacy Control are
        always honoured.
      </p>

      <h2 id="use">How we use it</h2>
      <ul>
        <li>To provide the service: search your notes, write cited answers and quizzes, and let you share courses.</li>
        <li>To keep it secure: sign-in sessions, rate limits, bot checks and the audit log.</li>
        <li>To improve it, using anonymous analytics only if you opted in.</li>
      </ul>
      <p>We do not use your material to train models, and we do not sell or rent data to anyone.</p>

      <h2 id="processors">Who we share data with</h2>
      <ul>
        <li>
          <strong>AI model provider</strong> (Google Gemini or Anthropic Claude, depending on how this
          instance is configured): receives your question and the few excerpts of your notes needed to
          answer it, and images of handwritten or scanned pages to transcribe them. Under Google&rsquo;s free Gemini API tier, Google may use submitted content to
          improve its products and it may be read by human reviewers; paid tiers and Anthropic&rsquo;s
          API do not use API data for training by default. Avoid uploading sensitive personal
          information.
        </li>
        <li>
          <strong>Cloudflare Turnstile</strong>, if enabled on this instance: checks that sign-up and
          log-in come from a person, and processes technical data about your browser to do so.
        </li>
        <li>
          <strong>Classmates you invite</strong> can read the courses you share with them, until you
          revoke the link or remove them.
        </li>
      </ul>
      <p>These providers may process data outside India.</p>

      <h2 id="cookies">Cookies</h2>
      <p>We use only these cookies, all strictly necessary to keep you signed in:</p>
      <ul>
        <li>
          <strong>access_token</strong>: your sign-in session (15 minutes, HTTP-only, secure).
        </li>
        <li>
          <strong>refresh_token</strong>: renews your session (30 days, HTTP-only, secure, sent only to
          sign-in endpoints).
        </li>
        <li>
          <strong>signed_in</strong>: contains only &ldquo;1&rdquo; so pages can show the right menu (30 days).
        </li>
      </ul>
      <p>
        Your cookie choice is remembered in your browser&rsquo;s local storage, not in a cookie.
        Analytics use no cookies at all. You can change your choice any time with &ldquo;Cookie
        settings&rdquo; at the bottom of every page.
      </p>

      <h2 id="retention">How long we keep it</h2>
      <ul>
        <li>Account and study material: until you delete them or your account. Deletion is immediate.</li>
        <li>Cached answers: up to 24 hours.</li>
        <li>Rate-limit counters: minutes up to one day.</li>
        <li>Audit log and anonymous analytics: up to 12 months.</li>
      </ul>

      <h2 id="rights">Your rights</h2>
      <p>
        In line with India&rsquo;s Digital Personal Data Protection Act, 2023 and similar laws, you can:
      </p>
      <ul>
        <li>
          <strong>Access</strong> your data: download it from your <Link href="/account">account page</Link>.
        </li>
        <li>
          <strong>Erase</strong> it: delete your account from the same page; everything goes at once.
        </li>
        <li>
          <strong>Correct</strong> it, <strong>withdraw consent</strong> or <strong>raise a grievance</strong>:
          email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. We reply within 30 days.
        </li>
      </ul>

      <h2 id="security">Security</h2>
      <p>
        Data is encrypted in transit (HTTPS). Each course is isolated by the application and again by
        database row-level security. Passwords are hashed with Argon2id. No system is perfectly
        secure; if you find a vulnerability, please report it to {CONTACT_EMAIL}.
      </p>

      <h2 id="children">Children</h2>
      <p>{SITE_NAME} is meant for college and university students. It is not directed at children under 18.</p>

      <h2 id="changes">Changes</h2>
      <p>
        If this policy changes in a way that affects you, we will update the date above and, for
        significant changes, tell signed-in users in the app.
      </p>
    </LegalPage>
  );
}
