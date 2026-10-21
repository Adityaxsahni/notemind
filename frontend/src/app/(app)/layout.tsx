// Signed-in app pages and the auth forms: a centred working area, kept out of search engines.
import type { Metadata } from "next";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function AppLayout({ children }: LayoutProps<"/">) {
  return <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">{children}</div>;
}
