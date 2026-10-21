# Design system

The visual and UX rules for the frontend. Tokens live in `frontend/src/app/globals.css`,
shared pieces in `frontend/src/components/ui.tsx`.

## Direction

Editorial and warm, like a well-kept notebook: paper-coloured backgrounds, ink text, one
vermilion accent, big serif headlines with an italic word, small uppercase mono labels, and
hatched sand tiles in place of photography. Taken from the city-explorer design handoff and
applied to studying: the course picker mirrors its city cards ("Enter"), an answer is laid
out like its place-detail screen (tags, an info grid, a quote), and the handwriting section
borrows its map (grid paper, a pin, a dark tooltip).

## Colour

Light only, as in the handoff (`color-scheme: light`).

| Token | Value | Use |
|---|---|---|
| `--background` | `#f6f1e7` | paper: the page |
| `--surface` / `--surface-2` | `#fefdf9` / `#fcf7eb` | cards / a highlighted cell |
| `--chip` | `#ebe4d4` | filled tags |
| `--foreground` | `#1c1b17` | ink: headings, primary buttons (15.3:1) |
| `--ink-soft` | `#4a473f` | body copy (8.2:1) |
| `--muted` | `#5f5a4f` | metadata, labels (6.1:1) |
| `--faint` | `#a39d90` | decoration only: dashed outlines, never informative text |
| `--accent` | `#c8391c` | vermilion: eyebrows, "Enter", citations (4.6:1 as text, 5.2:1 behind white) |
| `--stripe-a` / `--stripe-b` | `#dcd4c0` / `#cfc7b3` | hatched tiles |
| `--sage`, `--amber` | `#c7d3bf`, `#d9a21b` | map area, "right now" dot |
| `--danger`, `--success`, `--warning` | | status, always with text |

Rules: informative text meets WCAG AA (4.5:1) on paper and on cards; Playwright runs axe on
every public page. Vermilion text is never placed on `--chip` (4.1:1). Colour never carries
meaning alone (status dots always have a label).

## Typography

Self-hosted by `next/font` (`display: swap`):

| Role | Font | Class |
|---|---|---|
| Headlines | Instrument Serif, with italic `<em>` for the emphasised word | `.display` |
| Labels | JetBrains Mono, 11px, uppercase, 0.14em tracking, vermilion | `.eyebrow` |
| Metadata | JetBrains Mono, 12px, muted ("412 pages · 1,180 passages") | `.meta` |
| Grid labels | JetBrains Mono, 10px, uppercase ("OPEN TILL") | `.label-mono` |
| Body | Inter | default |

## Components

- **Buttons** (`Button`): pills. `primary` ink with paper text; `accent` vermilion ("Enter",
  "go"); `secondary` outlined; round outlined icon buttons for back and arrows. Minimum
  touch target 44 × 44 px.
- **Chips** (`Chip`): `active` ink, `outline` for filters, `tag` filled sand, `accent` the
  red uppercase mono badge ("PICKED FROM YOUR NOTES").
- **Hatched tiles** (`HatchTile`): diagonal stripes standing in for images, with a
  typewriter caption (`.tile-caption`).
- **Cards:** `rounded-2xl`, 1px border; the selected or first card gets a 1.5px ink border;
  "coming soon" cards are dashed.
- **Info grid:** 2 columns with hairline dividers, mono label above a bold value.
- **Forms:** mono label above the field, inline error under it (`aria-invalid` +
  `aria-describedby`), validated on blur and submit.

## Motion

Hero elements rise in on load; sections slide (never fade) into place on scroll with CSS
scroll-driven animations; cards lift on hover; the map pin pulses. All of it stops under
`prefers-reduced-motion: reduce`.

## Layout and responsiveness

Mobile first. Max width 6xl (72rem). The header collapses to a menu button below `md`, and
the menu shows serif links. No horizontal scrolling at 360px (Playwright checks this).

## Accessibility checklist

Skip link, landmarks (`header`, labelled `nav`, `main`, `footer`), one `h1` per page, visible
ink focus ring, form errors announced, alt text or `aria-hidden` on every graphic, axe clean
on all public pages (Playwright).
