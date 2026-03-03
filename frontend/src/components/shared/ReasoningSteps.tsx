import Markdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Typography } from "antd";
import { jsonToMarkdown } from "../../lib/json-to-markdown";

const { Text } = Typography;

export function ReasoningSteps({ steps }: { steps: unknown[] }) {
  if (!steps || steps.length === 0) {
    return <Text type="secondary">No reasoning steps</Text>;
  }

  return (
    <ol style={{ paddingLeft: 20, margin: 0 }}>
      {steps.map((step, i) => {
        const md =
          typeof step === "string" ? step : jsonToMarkdown(step, 4, "", "Step");

        return (
          <li key={i} style={{ marginBottom: 12 }}>
            <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {md}
            </Markdown>
          </li>
        );
      })}
    </ol>
  );
}
