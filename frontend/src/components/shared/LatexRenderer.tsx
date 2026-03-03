import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

/**
 * Render a string that may contain inline LaTeX ($...$) and display LaTeX ($$...$$).
 * Falls back to plain text if KaTeX parsing fails.
 */
export function LatexRenderer({ text }: { text: string }) {
  const html = useMemo(() => renderLatex(text), [text]);
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

function renderLatex(input: string): string {
  // First handle display math $$...$$
  let result = input.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false });
    } catch {
      return `$$${tex}$$`;
    }
  });

  // Then handle inline math $...$
  result = result.replace(/\$([^$\n]+?)\$/g, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false });
    } catch {
      return `$${tex}$`;
    }
  });

  return result;
}
