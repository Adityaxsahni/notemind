import type { SVGProps } from "react";

// Inline SVG icons (24px grid, stroke-based): no icon font or image requests.

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      width={24}
      height={24}
      {...props}
    >
      {children}
    </svg>
  );
}

export const UploadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 16V4m0 0-4 4m4-4 4 4" />
    <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
  </Icon>
);

export const ChatIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" />
    <path d="M8.5 11h7M8.5 14h4" />
  </Icon>
);

export const QuizIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="m8 9 1.5 1.5L12 8M8 15l1.5 1.5L12 14M14 9h2M14 15h2" />
  </Icon>
);

export const ShareIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3" />
    <path d="M3 20a6 6 0 0 1 12 0" />
    <path d="M16 11a3 3 0 1 0 0-6M21 20a6 6 0 0 0-4-5.6" />
  </Icon>
);

export const CiteIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 3h9l4 4v14H6z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </Icon>
);

export const ShieldIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3 5 6v5c0 4.4 3 8.4 7 10 4-1.6 7-5.6 7-10V6z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
);

export const BoltIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M13 3 5 14h6l-1 7 8-11h-6z" />
  </Icon>
);

export const SearchOffIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6" />
    <path d="m20 20-4.2-4.2M9 9l4 4M13 9l-4 4" />
  </Icon>
);

export const MenuIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Icon>
);

export const CloseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
);

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 12h14m-5-5 5 5-5 5" />
  </Icon>
);

export const DocumentIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </Icon>
);

export const SlidesIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="12" rx="2" />
    <path d="M12 16v4M8 20h8M7 12l3-3 2 2 4-4" />
  </Icon>
);

export const CameraIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
    <circle cx="12" cy="13" r="3.5" />
  </Icon>
);

export const PenIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20l4-1 11-11a2.1 2.1 0 0 0-3-3L5 16z" />
    <path d="M14 7l3 3M4 20h16" />
  </Icon>
);

export const SigmaIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M18 6V4H6l7 8-7 8h12v-2" />
  </Icon>
);

export const BookIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
    <path d="M4 21V5M8 7h7M8 11h5" />
  </Icon>
);

export function Logo({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={className} width={28} height={28}>
      <rect width="32" height="32" rx="9" fill="#1c1b17" />
      <path d="M9.5 23V9.5l13 13V9" fill="none" stroke="#f6f1e7" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="24.5" cy="24.5" r="2.6" fill="#c8391c" />
    </svg>
  );
}

/* Illustrations for the feature cards, in the paper-and-ink style: hatched sand tiles,
   cream cards with ink text lines, one vermilion detail. */

const INK = "#1c1b17";
const PAPER = "#fefdf9";
const RED = "#c8391c";
const SAND = "#ebe4d4";

function Scene({ children, label, caption }: { children: React.ReactNode; label: string; caption: string }) {
  const id = `hatch-${caption.replace(/\W+/g, "-")}`;
  return (
    <svg viewBox="0 0 240 150" role="img" aria-label={label} className="h-auto w-full">
      <defs>
        <pattern id={id} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="10" height="10" fill="#dcd4c0" />
          <rect width="3" height="10" fill="#cfc7b3" />
        </pattern>
      </defs>
      <rect width="240" height="150" rx="14" fill={`url(#${id})`} />
      {children}
      <rect x="10" y="128" width={caption.length * 5.2 + 12} height="13" rx="3" fill="#f6f1e7" opacity=".92" />
      <text x="16" y="137.5" fontSize="7.5" fill="#4a473f" fontFamily="ui-monospace, monospace">
        {caption}
      </text>
    </svg>
  );
}

export const AskScene = () => (
  <Scene label="A question answered with a page citation" caption="ask · cited answer">
    <rect x="30" y="22" width="122" height="30" rx="15" fill={PAPER} stroke={INK} strokeOpacity=".15" />
    <rect x="44" y="34" width="84" height="5" rx="2.5" fill={INK} opacity=".55" />
    <rect x="70" y="62" width="142" height="54" rx="12" fill={PAPER} stroke={INK} strokeOpacity=".15" />
    <rect x="82" y="76" width="96" height="5" rx="2.5" fill={INK} opacity=".7" />
    <rect x="82" y="88" width="70" height="5" rx="2.5" fill={INK} opacity=".45" />
    <rect x="160" y="84" width="40" height="14" rx="7" fill={RED} />
    <text x="180" y="93.5" fontSize="7.5" textAnchor="middle" fill="#fff" fontFamily="ui-monospace, monospace">
      p.12
    </text>
  </Scene>
);

export const QuizScene = () => (
  <Scene label="A multiple-choice quiz with the right answer ticked" caption="quiz · 4 options">
    <rect x="58" y="14" width="124" height="106" rx="12" fill={PAPER} stroke={INK} strokeOpacity=".15" />
    {[0, 1, 2, 3].map((i) => (
      <g key={i}>
        <rect x="70" y={26 + i * 22} width="100" height="16" rx="8" fill={i === 1 ? INK : SAND} />
        <circle cx="80" cy={34 + i * 22} r="3.5" fill={i === 1 ? RED : INK} opacity={i === 1 ? 1 : 0.3} />
        <rect x="90" y={31.5 + i * 22} width={56 - i * 7} height="5" rx="2.5" fill={i === 1 ? PAPER : INK} opacity={i === 1 ? 0.9 : 0.3} />
      </g>
    ))}
  </Scene>
);

export const ShareScene = () => (
  <Scene label="Classmates sharing one course" caption="shared · read-only link">
    <path d="M60 60 L120 52 L180 64" stroke={INK} strokeWidth="2" strokeDasharray="4 4" fill="none" opacity=".5" />
    {[60, 120, 180].map((x, i) => (
      <g key={x}>
        <circle cx={x} cy={i === 1 ? 52 : 62} r="14" fill={i === 1 ? INK : PAPER} stroke={INK} strokeOpacity=".2" />
        <rect x={x - 26} y={i === 1 ? 74 : 84} width="52" height="20" rx="10" fill={PAPER} stroke={INK} strokeOpacity=".15" />
        <rect x={x - 16} y={i === 1 ? 82 : 92} width="32" height="4" rx="2" fill={INK} opacity=".4" />
      </g>
    ))}
    <circle cx="120" cy="52" r="4" fill={RED} />
  </Scene>
);

export const UploadScene = () => (
  <Scene label="PDF, slides, Word files and photos of handwritten notes going into NoteMind" caption="pdf · slides · handwriting">
    {[
      ["PDF", 22],
      ["PPT", 76],
      ["DOC", 130],
      ["JPG", 184],
    ].map(([label, x], i) => (
      <g key={label}>
        <rect x={x as number} y="26" width="40" height="52" rx="7" fill={PAPER} stroke={INK} strokeOpacity=".18" />
        {i === 3 ? (
          <path
            d={`M${(x as number) + 7} 44 q5 -6 9 0 t9 0 t9 0 M${(x as number) + 7} 54 q5 -6 9 0 t9 0`}
            stroke={INK}
            strokeWidth="1.6"
            fill="none"
            opacity=".7"
          />
        ) : (
          <rect x={(x as number) + 7} y="40" width="26" height="4" rx="2" fill={INK} opacity=".35" />
        )}
        <rect x={(x as number) + 6} y="60" width="28" height="12" rx="6" fill={i === 3 ? RED : INK} />
        <text x={(x as number) + 20} y="68.5" fontSize="7" textAnchor="middle" fill="#fff" fontFamily="ui-monospace, monospace">
          {label}
        </text>
      </g>
    ))}
    <path d="M120 88v22m0 0-7-7m7 7 7-7" stroke={INK} strokeWidth="2.4" fill="none" strokeLinecap="round" />
  </Scene>
);
