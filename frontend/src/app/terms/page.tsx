import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage } from "@/components/LegalPage";
import { CONTACT_EMAIL, SITE_NAME } from "@/lib/site";

export const metadata: Metadata = {
  title: "Terms and conditions",
  description: `The rules for using ${SITE_NAME}: your content, acceptable use, AI answers, and limits.`,
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms and conditions"
      intro={`By creating an account or using ${SITE_NAME} you agree to these terms. Please read them; they are short.`}
    >
      <h2 id="service">1. The service</h2>
      <p>
        {SITE_NAME} lets you upload your own study material, ask questions about it, and generate
        practice quizzes. It is a student project offered free of charge, as is, without guarantees
        of availability.
      </p>

      <h2 id="account">2. Your account</h2>
      <ul>
        <li>You must be at least 18, or have permission from a parent or guardian.</li>
        <li>Keep your password private; you are responsible for activity on your account.</li>
        <li>One person per account. Automated sign-ups and access by bots or scrapers are not allowed.</li>
      </ul>

      <h2 id="content">3. Your content</h2>
      <p>
        You keep all rights to what you upload. You give us permission to store and process it only
        to provide the service to you and to the classmates you choose to share it with. Upload only
        material you have the right to use, such as your own notes or course material your
        institution lets you use for study.
      </p>

      <h2 id="use">4. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>upload unlawful, infringing, malicious or sexually explicit content, or other people&rsquo;s personal data without permission;</li>
        <li>try to access other users&rsquo; data, probe or break security, or bypass rate limits and bot checks;</li>
        <li>overload the service, or use it to build a competing dataset;</li>
        <li>use {SITE_NAME} during an exam or assessment, or in any way that breaks your institution&rsquo;s academic-integrity rules.</li>
      </ul>

      <h2 id="ai">5. AI-generated answers</h2>
      <p>
        Answers and quizzes are written by an AI model from excerpts of your notes. They can be
        incomplete or wrong, even with citations. Check important facts against the cited pages and
        your course material. {SITE_NAME} is a revision aid, not a substitute for your teachers or
        textbooks, and not professional advice.
      </p>

      <h2 id="limits">6. Limits</h2>
      <p>
        Files can be up to 200 MB and 2,000 pages, with 1 GB of storage per account. Daily question
        limits apply to keep the service available to everyone. We may change limits to protect the
        service.
      </p>

      <h2 id="termination">7. Ending your use</h2>
      <p>
        You can delete your account at any time from your <Link href="/account">account page</Link>.
        We may suspend accounts that break these terms or put other users at risk.
      </p>

      <h2 id="liability">8. Liability</h2>
      <p>
        To the extent the law allows, {SITE_NAME} is provided without warranties, and we are not
        liable for indirect losses, lost data, or the results of relying on AI-generated answers.
        Keep your own copies of important files.
      </p>

      <h2 id="privacy">9. Privacy</h2>
      <p>
        How we handle personal data is described in the <Link href="/privacy">privacy policy</Link>,
        which is part of these terms.
      </p>

      <h2 id="changes">10. Changes and contact</h2>
      <p>
        We may update these terms; the date above shows the latest version, and continued use after a
        change means you accept it. Questions: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalPage>
  );
}
