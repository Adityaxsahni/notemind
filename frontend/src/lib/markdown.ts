// Text preparation for rendering model output as Markdown with LaTeX math. Pure functions,
// kept apart from the React renderer so they can be unit-tested without a DOM.

const CITATION = /(\[S\d+\])/;

/** Split answer text into plain text and [S#] markers. */
export function splitCitations(text: string): Array<{ text: string; sourceId?: string }> {
  return text
    .split(CITATION)
    .filter(Boolean)
    .map((part) => {
      const match = /^\[(S\d+)\]$/.exec(part);
      return match ? { text: part, sourceId: match[1] } : { text: part };
    });
}

export const CITATION_HREF = "#cite-";

/**
 * Normalise what models write into what remark-math reads, and turn [S#] markers into
 * links the renderer shows as page chips:
 * - \( … \) → $…$ and \[ … \] → $$…$$ (both LaTeX conventions are common in model output)
 * - [S1] → [S1](#cite-S1)
 */
export function prepareMarkdown(text: string): string {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, math: string) => `\n$$\n${math.trim()}\n$$\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, math: string) => `$${math.trim()}$`)
    .replace(/\[(S\d+)\](?!\()/g, (_, id: string) => `[${id}](${CITATION_HREF}${id})`);
}
