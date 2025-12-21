/* eslint-disable */
export function normalizeMarkdown(input: string): string {
  let text = input || "";
  // Normalize bullets to '-'
  text = text.replace(/^[ \t]*[•*]\s+/gm, "- ");
  // Autonumber ordered lists
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (/^[ \t]*\d+\.[ \t]+/.test(lines[i])) continue;
    if (/^[ \t]*\(?\d+\)?[)\.]\s+/.test(lines[i])) {
      lines[i] = lines[i].replace(/^[ \t]*\(?\d+\)?[)\.]\s+/, `${i + 1}. `);
    }
  }
  text = lines.join("\n");
  // Normalize code fences ```lang ... ```
  text = text.replace(/```\s*\n([\s\S]*?)\n```/g, "```\n$1\n```");
  // Convert Note:/Warning:/Tip: to blockquote with role
  text = text.replace(
    /^(Note|Warning|Tip):\s*/gim,
    (_m, role) => `> **${role}:** `,
  );
  // Collapse >2 blank lines
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}

export function beautifyMarkdown(input: string): string {
  // Idempotent
  const once = normalizeMarkdown(input);
  return normalizeMarkdown(once);
}
