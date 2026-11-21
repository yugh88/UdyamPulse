import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { ensureAccessToken, post } from "./api";
import { useAuth } from "./auth";
import type { ChangeEvent } from "./types";

/** Query keys that change events can make stale. */
const STALE_ON_CHANGE = ["applications", "application", "changes", "alerts", "alert", "portfolio", "migration", "nav-counts", "msme"];

/** Marks items as seen (`POST /v1/seen`), which clears their change markers, then refreshes what shows them. */
export function useMarkSeen() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { entity_type: "application" | "alert"; ids?: (string | number)[]; all?: boolean }) =>
      post("/seen", { entity_type: body.entity_type, ids: (body.ids ?? []).map(String), all: !!body.all }),
    onSuccess: (_r, body) => {
      const keys = body.entity_type === "application" ? ["applications", "changes", "nav-counts"] : ["alerts", "alert", "nav-counts"];
      keys.forEach((k) => void qc.invalidateQueries({ queryKey: [k] }));
    },
  });
}

/** Plain-language toast text for a live change, e.g. "Score updated · 698 → 723". */
export function changeToast(e: ChangeEvent): string {
  const b = e.before?.score as number | null | undefined;
  const a = e.after?.score as number | null | undefined;
  if ((e.event_type === "scored" || e.event_type === "score_changed") && a != null) return b != null ? `Score updated · ${b} → ${a}` : `Scored ${a}`;
  return e.summary;
}

/** Parses `event:` / `data:` blocks from a Server-Sent Events byte stream. */
async function* sse(body: ReadableStream<Uint8Array>): AsyncGenerator<{ event: string; data: string }> {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += value;
    let cut: number;
    while ((cut = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (data.length) yield { event, data: data.join("\n") };
    }
  }
}

/**
 * Live updates: listens to `GET /v1/events?changes=1` (scoped to the user's branch or factory), refreshes the
 * affected queries, and shows a short dark toast for changes made by someone else (your own actions already have
 * their own confirmation). If streaming is unavailable it simply retries later; screens still refresh on focus.
 */
export function useLiveChanges() {
  const qc = useQueryClient();
  const { session } = useAuth();
  const me = session?.username;
  const pending = useRef<number | null>(null);

  useEffect(() => {
    if (!me) return;
    const ctl = new AbortController();
    let stopped = false;

    const refresh = () => {
      if (pending.current) return;
      pending.current = window.setTimeout(() => {
        pending.current = null;
        STALE_ON_CHANGE.forEach((k) => void qc.invalidateQueries({ queryKey: [k] }));
      }, 400);
    };

    (async () => {
      while (!stopped) {
        try {
          const token = await ensureAccessToken();
          if (!token) return;
          const res = await fetch("/api/v1/events?changes=1", { headers: { Authorization: `Bearer ${token}` }, signal: ctl.signal });
          if (!res.ok || !res.body) throw new Error(String(res.status));
          for await (const msg of sse(res.body)) {
            if (msg.event !== "change") continue;
            const e = JSON.parse(msg.data) as ChangeEvent;
            refresh();
            if (e.actor && e.actor !== me) toast.success(changeToast(e));
          }
        } catch {
          if (ctl.signal.aborted) return;
        }
        // The server closes long streams; reconnect after a pause.
        await new Promise((r) => setTimeout(r, 3000));
      }
    })();

    return () => {
      stopped = true;
      ctl.abort();
      if (pending.current) window.clearTimeout(pending.current);
    };
  }, [me, qc]);
}
