import { describe, expect, it } from "vitest";
import en from "./en";
import hi from "./hi";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) => (typeof v === "object" ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`]));
}
function leaves(obj: object): string[] {
  return Object.values(obj).flatMap((v) => (typeof v === "object" ? leaves(v as object) : [String(v)]));
}

describe("MSME app translations", () => {
  it("has a Hindi string for every English string", () => {
    expect(keys(hi).sort()).toEqual(keys(en).sort());
  });
  it("keeps the same placeholders in both languages", () => {
    const vars = (s: string) => [...s.matchAll(/{{(\w+)}}/g)].map((m) => m[1]).sort();
    const e = leaves(en);
    const h = leaves(hi);
    e.forEach((s, i) => expect(vars(h[i])).toEqual(vars(s)));
  });
});
