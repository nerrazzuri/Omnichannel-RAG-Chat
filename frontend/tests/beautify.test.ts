import { beautifyMarkdown } from "../src/lib/beautify";

describe("beautifyMarkdown", () => {
  it("is idempotent and normalizes bullets", () => {
    const input = `• item 1\n* item 2\n- item 3`;
    const once = beautifyMarkdown(input);
    const twice = beautifyMarkdown(once);
    expect(twice).toBe(once);
    expect(once.split("\n").every((l) => l.trimStart().startsWith("- "))).toBe(
      true,
    );
  });

  it("normalizes code fences", () => {
    const input = "```\nconsole.log(1)\n```";
    const out = beautifyMarkdown(input);
    expect(out.includes("```")).toBe(true);
  });
});
