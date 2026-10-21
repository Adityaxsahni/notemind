import type { Metadata, Viewport } from "next";
import { Inter, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import { Suspense } from "react";

import "./globals.css";

import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { Analytics, CookieBanner, ErrorReporter } from "@/components/SiteChrome";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

// Self-hosted at build time by next/font: no request to Google from visitors' browsers.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
// Editorial serif for headlines (with its italic), mono for labels and metadata.
const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
  display: "swap",
});
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jetbrains-mono", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME}: answers from your own notes`, template: `%s · ${SITE_NAME}` },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: ["study assistant", "course notes", "RAG", "quiz generator", "exam revision", "citations"],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: `${SITE_NAME}: answers from your own notes`,
    description: SITE_DESCRIPTION,
    url: "/",
    locale: "en_IN",
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE_NAME}: answers from your own notes`,
    description: SITE_DESCRIPTION,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f6f1e7",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${serif.variable} ${mono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-full focus:bg-foreground focus:px-4 focus:py-2 focus:text-background"
        >
          Skip to content
        </a>
        <Suspense>
          <Header />
        </Suspense>
        <main id="main" className="w-full flex-1">
          {children}
        </main>
        <Footer />
        <CookieBanner />
        <Suspense>
          <Analytics />
        </Suspense>
        <ErrorReporter />
      </body>
    </html>
  );
}
