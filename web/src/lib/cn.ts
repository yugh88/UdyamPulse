import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge must know our custom font size (`text-13`, defined in the theme). Without this it read
// `text-13` as a text colour and silently dropped `text-on-primary` from small primary buttons.
const twMerge = extendTailwindMerge({ extend: { theme: { text: ["13"] } } });

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
