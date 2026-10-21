import type { Citation } from "@/lib/types";

const CITATION = /(\[S\d+\])/;

/** Split answer text into plain text and [S#] markers (exported for tests). */
export function splitCitations(text: string): Array<{ text: string; sourceId?: string }> {
  return text
    .split(CITATION)
    .filter(Boolean)
    .map((part) => {
      const match = /^\[(S\d+)\]$/.exec(part);
      return match ? { text: part, sourceId: match[1] } : { text: part };
    });
}

/**
 * Renders model output as React text nodes only, never as HTML, so nothing an uploaded
 * document smuggles into an answer can become markup or script (threat T7).
 */
export function AnswerText({ text, citations }: { text: string; citations: Citation[] }) {
  const byId = new Map(citations.map((c) => [c.id, c]));
  return (
    <p className="whitespace-pre-wrap leading-7">
      {splitCitations(text).map((part, i) => {
        if (!part.sourceId) return <span key={i}>{part.text}</span>;
        const citation = byId.get(part.sourceId);
        const label = citation ? `${citation.document_title}, page ${citation.page}` : part.sourceId;
        return (
          <a
            key={i}
            href={citation ? `#cite-${citation.id}` : undefined}
            title={label}
            className="mx-0.5 inline-flex -translate-y-px items-center rounded bg-accent-soft px-1.5 font-mono text-xs text-accent no-underline"
          >
            {citation ? `p.${citation.page}` : part.sourceId}
          </a>
        );
      })}
    </p>
  );
}
