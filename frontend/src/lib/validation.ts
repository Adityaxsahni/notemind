// Client-side checks give instant feedback; the backend re-validates everything (it never
// trusts the browser). Keep these in step with backend/app/schemas.py.

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function emailProblem(email: string): string | null {
  if (!email.trim()) return "Enter your email address.";
  if (!EMAIL.test(email.trim())) return "That doesn't look like an email address.";
  return null;
}

export function passwordProblem(password: string, email: string, isSignup: boolean): string | null {
  if (!password) return "Enter your password.";
  if (!isSignup) return null; // login must not reveal the password policy
  if (password.length < 10) return "Use at least 10 characters.";
  if (password.length > 128) return "Use at most 128 characters.";
  if (new Set(password).size < 5) return "Use a less repetitive password.";
  const local = email.split("@")[0]?.toLowerCase() ?? "";
  if (local.length >= 4 && password.toLowerCase().includes(local)) {
    return "Don't include your email address in the password.";
  }
  return null;
}

/** 0-4: a rough guide shown while typing, not a policy. */
export function passwordStrength(password: string): number {
  let score = 0;
  if (password.length >= 10) score++;
  if (password.length >= 14) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score++;
  return score;
}

const CONTROL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f‪-‮⁦-⁩]/;

export function textProblem(value: string, label: string, max: number): string | null {
  const trimmed = value.trim();
  if (!trimmed) return `Enter a ${label}.`;
  if (trimmed.length > max) return `Keep the ${label} under ${max} characters.`;
  if (CONTROL.test(trimmed)) return `The ${label} contains characters that aren't allowed.`;
  return null;
}
