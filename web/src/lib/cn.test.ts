import { describe, expect, it } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  it("keeps the text colour next to the custom 13px size", () => {
    const out = cn("bg-primary text-on-primary hover:bg-primary-hover", "h-8 px-2.5 text-13");
    expect(out).toContain("text-on-primary");
    expect(out).toContain("text-13");
  });
  it("still lets a later size replace an earlier one", () => {
    expect(cn("text-sm", "text-13")).toBe("text-13");
  });
});
