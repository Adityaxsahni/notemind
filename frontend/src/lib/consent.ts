// Cookie/analytics consent, stored in this browser only. NoteMind's own cookies (the login
// session and a "signed in" hint) are strictly necessary and need no consent; analytics are
// cookieless but still opt-in.

export type Consent = "accepted" | "essential";

const KEY = "notemind-consent-v1";
export const CONSENT_EVENT = "notemind:consent";
export const OPEN_SETTINGS_EVENT = "notemind:cookie-settings";

export function readConsent(): Consent | null {
  try {
    const value = window.localStorage.getItem(KEY);
    return value === "accepted" || value === "essential" ? value : null;
  } catch {
    return null; // storage blocked: ask again, track nothing
  }
}

export function saveConsent(value: Consent): void {
  try {
    window.localStorage.setItem(KEY, value);
  } catch {
    // storage blocked: the choice applies to this page view only
  }
  window.dispatchEvent(new CustomEvent(CONSENT_EVENT, { detail: value }));
}

/** Browser-level opt-outs win over any banner choice. */
export function trackingBlocked(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.doNotTrack === "1" || nav.globalPrivacyControl === true;
}

export function isSignedIn(): boolean {
  return document.cookie.split("; ").includes("signed_in=1");
}

/** useSyncExternalStore plumbing: consent lives in localStorage, outside React. */
export function subscribeConsent(onChange: () => void): () => void {
  window.addEventListener(CONSENT_EVENT, onChange);
  window.addEventListener("storage", onChange); // another tab changed it
  return () => {
    window.removeEventListener(CONSENT_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Cookies have no change event; the header re-reads on every render (each navigation). */
export const subscribeNothing = () => () => {};
