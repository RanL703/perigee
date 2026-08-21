import type { ReactNode } from "react";

// Minimal inline markdown: **bold**, *italic*, `code`.
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g);
  return parts.filter(Boolean).map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return <span key={key}>{part}</span>;
  });
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "h"; text: string };

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let current: Block | null = null;
  const flush = () => {
    if (current) blocks.push(current);
    current = null;
  };
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      flush();
      continue;
    }
    const heading = line.match(/^#{1,4}\s+(.*)/);
    if (heading) {
      flush();
      blocks.push({ kind: "h", text: heading[1] });
      continue;
    }
    const bullet = line.match(/^[-*•]\s+(.*)/);
    const ordered = line.match(/^\d+[.)]\s+(.*)/);
    if (bullet) {
      if (current?.kind !== "ul") flush();
      if (current?.kind === "ul") current.items.push(bullet[1]);
      else current = { kind: "ul", items: [bullet[1]] };
      continue;
    }
    if (ordered) {
      if (current?.kind !== "ol") flush();
      if (current?.kind === "ol") current.items.push(ordered[1]);
      else current = { kind: "ol", items: [ordered[1]] };
      continue;
    }
    if (current?.kind === "p") current.lines.push(line);
    else {
      flush();
      current = { kind: "p", lines: [line] };
    }
  }
  flush();
  return blocks;
}

export function Markdown({ text }: { text: string }) {
  // Models frequently emit malformed emphasis like "*Heading:**"; normalize
  // it to proper "**bold**" pairs so no raw asterisks reach the screen.
  const normalized = text.replace(/(^|[\s(])\*([^*\n]+?)\*\*/g, "$1**$2**");
  return (
    <>
      {parseBlocks(normalized).map((block, index) => {
        const key = `b${index}`;
        if (block.kind === "h") return <span key={key} className="md-heading">{renderInline(block.text, key)}</span>;
        if (block.kind === "ul")
          return (
            <ul key={key}>
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
              ))}
            </ul>
          );
        if (block.kind === "ol")
          return (
            <ol key={key}>
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
              ))}
            </ol>
          );
        return <p key={key}>{renderInline(block.lines.join(" "), key)}</p>;
      })}
    </>
  );
}
