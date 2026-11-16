import { useEffect, useRef } from "react";

function typing(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/**
 * Global shortcuts. Keys are single characters ("?") or two-key sequences ("g c").
 * "mod+k" means ⌘K on macOS and Ctrl+K elsewhere, and works while typing.
 */
export function useHotkeys(map: Record<string, () => void>) {
  const ref = useRef(map);
  ref.current = map;
  useEffect(() => {
    let prefix: string | null = null;
    let timer: number | undefined;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey) {
        const combo = `mod+${e.key.toLowerCase()}`;
        if (ref.current[combo]) {
          e.preventDefault();
          ref.current[combo]();
        }
        return;
      }
      if (e.altKey || typing(e)) return;
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (prefix) {
        const seq = `${prefix} ${key}`;
        prefix = null;
        window.clearTimeout(timer);
        if (ref.current[seq]) {
          e.preventDefault();
          ref.current[seq]();
        }
        return;
      }
      if (ref.current[e.key]) {
        e.preventDefault();
        ref.current[e.key]();
        return;
      }
      if (Object.keys(ref.current).some((k) => k.startsWith(`${key} `))) {
        prefix = key;
        timer = window.setTimeout(() => (prefix = null), 1200);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(timer);
    };
  }, []);
}
