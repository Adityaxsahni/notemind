"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { getMe, logout } from "@/lib/api";
import { isSignedIn, subscribeNothing } from "@/lib/consent";
import type { User } from "@/lib/types";

import { CloseIcon, Logo, MenuIcon } from "./icons";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/features", label: "Features" },
];

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const signedIn = useSyncExternalStore(subscribeNothing, isSignedIn, () => false);
  const [user, setUser] = useState<User | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null); // open on this path only
  const menuOpen = menuFor === pathname;

  useEffect(() => {
    if (!signedIn) return;
    getMe()
      .then(setUser)
      .catch(() => setUser(null)); // app pages redirect to sign-in themselves
  }, [signedIn, pathname]);

  async function signOut() {
    await logout().catch(() => undefined);
    setUser(null);
    router.replace("/login");
  }

  const links = signedIn ? [...NAV, { href: "/courses", label: "Your courses" }] : NAV;
  const linkClass = (href: string) =>
    `rounded-full px-3.5 py-1.5 text-sm transition ${
      pathname === href ? "bg-foreground text-background" : "text-ink-soft hover:bg-chip"
    }`;

  const actions = signedIn ? (
    <>
      <Link href="/account" className="meta max-w-48 truncate px-3 py-2 hover:text-foreground" title="Account">
        {(signedIn && user?.email) || "Account"}
      </Link>
      <button
        type="button"
        onClick={signOut}
        className="rounded-full border border-foreground/25 px-4 py-2 text-sm font-medium hover:border-foreground"
      >
        Sign out
      </button>
    </>
  ) : (
    <>
      <Link href="/login" className="rounded-full border border-foreground/25 px-5 py-2 text-sm font-medium transition hover:border-foreground">
        Log in
      </Link>
      <Link href="/signup" className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background transition hover:bg-foreground/85">
        Sign up
      </Link>
    </>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <Logo />
          <span className="display text-2xl">NoteMind</span>
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className={linkClass(l.href)} aria-current={pathname === l.href ? "page" : undefined}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">{actions}</div>

        <button
          type="button"
          className="grid size-11 place-items-center rounded-full border border-foreground/25 md:hidden"
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          onClick={() => setMenuFor(menuOpen ? null : pathname)}
        >
          {menuOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>

      {menuOpen && (
        <div id="mobile-menu" className="animate-rise border-t border-border bg-background px-4 pb-6 pt-2 md:hidden">
          <nav aria-label="Mobile" className="flex flex-col">
            {links.map((l) => (
              <Link key={l.href} href={l.href} className="display rounded-lg px-2 py-2.5 text-3xl hover:text-accent">
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="mt-3 flex flex-wrap items-center gap-2">{actions}</div>
        </div>
      )}
    </header>
  );
}
