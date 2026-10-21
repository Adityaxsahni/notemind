"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Alert, Spinner } from "@/components/ui";
import { ApiError, acceptInvite } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";

function Join() {
  const token = useSearchParams().get("token");
  const router = useRouter();
  const handleError = useApiErrorHandler();
  const [error, setError] = useState<string | null>(token ? null : "This invite link is incomplete.");

  useEffect(() => {
    if (!token) return;
    acceptInvite(token)
      .then((collection) => router.replace(`/c/${collection.id}`))
      .catch((err) =>
        setError(
          err instanceof ApiError && err.status === 404
            ? "This invite link has expired or was revoked. Ask for a new one."
            : handleError(err), // 401 → sign in, then come back here
        ),
      );
  }, [token, router, handleError]);

  if (error) {
    return (
      <div className="mx-auto max-w-md space-y-4 pt-8">
        <Alert>{error}</Alert>
        <Link href="/" className="text-sm text-accent hover:underline">
          Go to your courses
        </Link>
      </div>
    );
  }
  return (
    <p className="flex items-center justify-center gap-2 pt-8 text-sm text-muted">
      <Spinner /> Joining…
    </p>
  );
}

export default function JoinPage() {
  return (
    <Suspense>
      <Join />
    </Suspense>
  );
}
