/**
 * Convert JSON data to markdown format.
 * Ported from fileserver/converters/json2md.py: json_to_markdown()
 */

export function jsonToMarkdown(
  data: unknown,
  level = 2,
  _key = "",
  listTitle = "Item"
): string {
  if (data === null || data === undefined) {
    return "*null*";
  }

  if (typeof data === "boolean") {
    return data ? "true" : "false";
  }

  if (typeof data === "number" || typeof data === "string") {
    return String(data);
  }

  const lines: string[] = [];

  if (Array.isArray(data)) {
    for (let i = 0; i < data.length; i++) {
      const item = data[i];
      if (typeof item === "object" && item !== null) {
        const heading = "#".repeat(Math.min(level, 6)) + " " + listTitle + " " + (i + 1);
        lines.push(heading, "");
        lines.push(jsonToMarkdown(item, level + 1, `item_${i + 1}`, listTitle));
        lines.push("");
      } else {
        lines.push(`- ${item}`);
      }
    }
  } else if (typeof data === "object") {
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      const heading =
        "#".repeat(Math.min(level, 6)) +
        " " +
        k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      lines.push(heading, "");
      lines.push(jsonToMarkdown(v, level + 1, k, listTitle));
      lines.push("");
    }
  }

  return lines.join("\n");
}
