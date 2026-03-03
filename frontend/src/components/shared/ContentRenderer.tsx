import Markdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { jsonToMarkdown } from "../../lib/json-to-markdown";

/**
 * Render node content — handles string, dict, and list content types.
 * Uses react-markdown with KaTeX for LaTeX math, ported from
 * fileserver/converters/json2md.py for structured content.
 */
export function ContentRenderer({
  content,
}: {
  content: string | Record<string, unknown> | unknown[];
}) {
  const md =
    typeof content === "string" ? content : jsonToMarkdown(content, 3);

  return (
    <div className="content-renderer" style={{ lineHeight: 1.7 }}>
      <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {md}
      </Markdown>
    </div>
  );
}
