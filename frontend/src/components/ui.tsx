import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "accent" | "secondary" | "danger" | "ghost";

// Pills, as in the design: ink for the main action, vermilion for "go", outlines otherwise.
const variants: Record<Variant, string> = {
  primary: "bg-foreground text-background hover:bg-foreground/85",
  accent: "bg-accent text-accent-foreground hover:bg-accent/90",
  secondary: "border border-foreground/25 bg-surface hover:border-foreground",
  danger: "border border-foreground/25 bg-surface text-danger hover:border-danger hover:bg-danger-soft",
  ghost: "text-muted hover:text-foreground",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm outline-none placeholder:text-muted focus:border-foreground focus:ring-2 focus:ring-foreground/10 ${className}`}
      {...props}
    />
  );
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor: string }) {
  return (
    <label htmlFor={htmlFor} className="label-mono mb-1.5 block">
      {children}
    </label>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-border bg-surface p-5 ${className}`}>
      {children}
    </section>
  );
}

export function Alert({
  children,
  tone = "error",
}: {
  children: ReactNode;
  tone?: "error" | "warning" | "info";
}) {
  const tones = {
    error: "bg-danger-soft text-danger",
    warning: "bg-warning-soft text-warning",
    info: "bg-chip text-foreground",
  };
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-xl px-3.5 py-2.5 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span
      role="status"
      aria-label={label}
      className="inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
    />
  );
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div
      className="h-1 w-full overflow-hidden rounded-full bg-chip"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="h-full bg-accent transition-all" style={{ width: `${value}%` }} />
    </div>
  );
}

/** Uppercase mono label in vermilion above a headline. */
export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`eyebrow ${className}`}>{children}</p>;
}

/** Rounded pill: "outline" for filters, "active" for the selected one, "tag" for traits. */
export function Chip({
  children,
  tone = "outline",
  className = "",
}: {
  children: ReactNode;
  tone?: "outline" | "active" | "tag" | "accent";
  className?: string;
}) {
  const tones = {
    outline: "border border-foreground/20 text-ink-soft",
    active: "bg-foreground text-background",
    tag: "bg-chip text-ink-soft",
    accent: "bg-accent font-mono uppercase tracking-[0.12em] text-accent-foreground text-[0.625rem]",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs ${tones[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** Hatched placeholder tile with an optional typewriter caption, in place of a photo. */
export function HatchTile({
  caption,
  className = "",
  children,
}: {
  caption?: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div aria-hidden className={`hatch relative overflow-hidden ${className}`}>
      {children}
      {caption && <span className="tile-caption absolute bottom-2 left-2">{caption}</span>}
    </div>
  );
}
