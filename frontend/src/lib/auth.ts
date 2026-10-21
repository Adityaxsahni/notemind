"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";

import { ApiError } from "./api";

/** Only same-site relative paths: never redirect to another origin after login. */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/courses";
}

/**
 * Returns a handler for API errors: a 401 (session expired even after refresh) sends the
 * user to sign in and back here afterwards; anything else becomes a message to show.
 */
export function useApiErrorHandler() {
  const router = useRouter();
  const pathname = usePathname();
  return useCallback(
    (error: unknown): string | null => {
      if (error instanceof ApiError && error.status === 401) {
        const here = pathname + window.location.search;
        router.replace(`/login?next=${encodeURIComponent(here)}`);
        return null;
      }
      if (error instanceof ApiError) return error.message;
      return "Something went wrong. Check your connection and try again.";
    },
    [router, pathname],
  );
}
