import { describe, expect, it } from "vitest";
import { crore, inr, lakh, num, pct, rupees, signed } from "./format";

describe("Indian number formatting", () => {
  it("groups in lakh and crore", () => {
    expect(num(1234567)).toBe("12,34,567");
    expect(rupees(1234567)).toBe("₹12,34,567");
    expect(rupees(-50000)).toBe("−₹50,000");
  });
  it("uses L and Cr helpers", () => {
    expect(lakh(250000)).toBe("2.5 L");
    expect(crore(30000000)).toBe("3.00 Cr");
    expect(inr(30000000)).toBe("₹3.00 Cr");
    expect(inr(250000)).toBe("₹2.5 L");
    expect(inr(99999)).toBe("₹99,999");
  });
  it("handles missing values", () => {
    expect(inr(null)).toBe("–");
    expect(num(undefined)).toBe("–");
    expect(pct(null)).toBe("–");
  });
  it("formats percentages and signed deltas", () => {
    expect(pct(0.0067, 2)).toBe("0.67%");
    expect(signed(12)).toBe("+12");
    expect(signed(-5)).toBe("−5");
    expect(signed(0)).toBe("0");
  });
});
