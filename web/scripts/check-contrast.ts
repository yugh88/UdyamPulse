/**
 * WCAG 2.2 AA contrast check for the design tokens in src/styles/tokens.css.
 * Body text pairs need 4.5:1; large text and UI components need 3:1.
 * Run: npm run check:contrast   (exits 1 on any failure)
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const css = readFileSync(fileURLToPath(new URL("../src/styles/tokens.css", import.meta.url)), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`selector ${selector} not found`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) out[m[1]] = m[2];
  return out;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// [foreground, background, minimum ratio]
const TEXT = 4.5;
const UI = 3;
const PAIRS: [string, string, number][] = [
  ...["bg", "surface", "surface-2"].flatMap((bg): [string, string, number][] => [
    ["text", bg, TEXT],
    ["text-muted", bg, TEXT],
    ["text-subtle", bg, UI], // captions/placeholders only (decorative or large)
    ["primary", bg, TEXT],
    ["success", bg, TEXT],
    ["warning", bg, TEXT],
    ["danger", bg, TEXT],
    ["info", bg, TEXT],
    ["brand", bg, TEXT], // change markers: "Updated" / "New" badges are text
    ["purple", bg, TEXT],
  ]),
  ["on-primary", "primary", TEXT],
  ["on-primary", "primary-hover", TEXT],
  ["on-primary", "danger", TEXT], // danger button
  ["primary", "primary-tint", TEXT],
  ["text", "primary-tint", TEXT],
  ["brand", "brand-tint", TEXT],
  ["purple", "purple-tint", TEXT],
  ["text", "surface-2", TEXT],
  ["on-toast", "toast", TEXT],
  ["success", "success-tint", TEXT],
  ["warning", "warning-tint", TEXT],
  ["danger", "danger-tint", TEXT],
  ["info", "info-tint", TEXT],
  ["border-strong", "surface", UI], // input outlines and focusable control edges
  ["border-strong", "bg", UI],
  ["primary", "surface", UI], // focus ring
  ...[1, 2, 3, 4, 5, 6].map((i): [string, string, number] => [`chart-${i}`, "surface", UI]),
];

let failures = 0;
for (const [name, selector] of [
  ["light", ":root"],
  ["dark", '[data-theme="dark"]'],
] as const) {
  const t = block(selector);
  for (const [fg, bg, min] of PAIRS) {
    if (!t[fg] || !t[bg]) {
      console.error(`✗ ${name}: token --${!t[fg] ? fg : bg} is missing`);
      failures++;
      continue;
    }
    const r = ratio(t[fg], t[bg]);
    if (r < min) {
      console.error(`✗ ${name}: --${fg} ${t[fg]} on --${bg} ${t[bg]} = ${r.toFixed(2)}:1 (needs ${min}:1)`);
      failures++;
    }
  }
}
if (failures) {
  console.error(`\n${failures} contrast failure(s)`);
  process.exit(1);
}
console.log(`contrast: ${PAIRS.length} pairs × 2 themes pass WCAG 2.2 AA`);
