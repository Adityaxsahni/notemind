import "katex/dist/katex.min.css";

import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { CITATION_HREF, prepareMarkdown } from "@/lib/markdown";
import type { Citation } from "@/lib/types";

// Model output is untrusted (an uploaded document can steer it, threat T7). It's rendered as
// Markdown into React elements: raw HTML is dropped (`skipHtml`), links other than our own
// citation chips become plain text (no phishing links), images are never loaded, and KaTeX
// runs with `trust: false`, so \href, \url and similar commands do nothing.
const KATEX = { throwOnError: false, strict: "ignore", trust: false, output: "htmlAndMathml" } as const;

function components(citations: Citation[]): Components {
  const byId = new Map(citations.map((c) => [c.id, c]));
  return {
    a({ href, children }) {
      if (!href?.startsWith(CITATION_HREF)) return <span>{children}</span>;
      const id = href.slice(CITATION_HREF.length);
      const citation = byId.get(id);
      const label = citation ? `${citation.document_title}, page ${citation.page}` : id;
      return (
        <a
          href={citation ? `#cite-${citation.id}` : undefined}
          title={label}
          className="mx-0.5 inline-flex -translate-y-px items-center rounded-full bg-accent px-1.5 align-baseline font-mono text-xs text-accent-foreground no-underline"
        >
          {citation ? `p.${citation.page}` : id}
        </a>
      );
    },
    img: () => null,
  };
}

/** A streamed or finished answer: Markdown with LaTeX math and [S#] citation chips. */
export function AnswerText({ text, citations }: { text: string; citations: Citation[] }) {
  return (
    <div className="answer">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, KATEX]]}
        components={components(citations)}
      >
        {prepareMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}

/** Short model-written text (quiz questions, options, explanations) with inline math. */
export function MathText({ children }: { children: string }): ReactNode {
  return (
    <span className="answer answer-inline">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeKatex, KATEX]]}
        components={{ ...components([]), p: ({ children: inner }) => <>{inner}</> }}
      >
        {prepareMarkdown(children)}
      </ReactMarkdown>
    </span>
  );
}
