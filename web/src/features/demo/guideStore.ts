import { useSyncExternalStore } from "react";

/** Guided-demo state shared by the launcher buttons and the panel; remembered across reloads. */
interface GuideState {
  open: boolean;
  step: number;
}

const KEY = "up_demo_guide";
let state: GuideState = read();
const listeners = new Set<() => void>();

function read(): GuideState {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { open: false, step: 0, ...JSON.parse(raw) } : { open: false, step: 0 };
  } catch {
    return { open: false, step: 0 };
  }
}

function write(next: Partial<GuideState>) {
  state = { ...state, ...next };
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* private mode: the guide still works for this tab */
  }
  listeners.forEach((l) => l());
}

export const guide = {
  open: (step?: number) => write({ open: true, ...(step === undefined ? {} : { step }) }),
  close: () => write({ open: false }),
  go: (step: number) => write({ step }),
};

export function useGuide(): GuideState {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
  );
}
