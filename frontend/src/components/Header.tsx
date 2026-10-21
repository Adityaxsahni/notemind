"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getMe, logout } from "@/lib/api";
import type { User } from "@/lib/types";

const PUBLIC_PATHS = ["/login", "/signup"];

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (isPublic) return;
    getMe()
      .then(setUser)
      .catch(() => setUser(null)); // pages handle redirecting to sign-in themselves
  }, [isPublic, pathname]);

  async function signOut() {
    await logout().catch(() => undefined);
    setUser(null);
    router.replace("/login");
  }

  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span aria-hidden className="grid size-7 place-items-center rounded-lg bg-accent text-accent-foreground text-sm">
            N
          </span>
          NoteMind
        </Link>
        {!isPublic && user && (
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/account" className="text-muted hover:text-foreground" title="Account">
              {user.email}
            </Link>
            <button onClick={signOut} className="text-muted hover:text-foreground">
              Sign out
            </button>
          </nav>
        )}
      </div>
    </header>
  );
}
