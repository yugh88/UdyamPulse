import { api, ApiError } from "./api";

export interface JobView<R = Record<string, unknown>> {
  id: string;
  kind: string;
  status: "queued" | "running" | "retrying" | "succeeded" | "failed" | "dead";
  progress: number;
  message: string | null;
  result: R | null;
  error: string | null;
  attempts: number;
  terminal: boolean;
}

export const ASYNC = { Prefer: "respond-async" };

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

async function follow<R>(jobId: string, onUpdate?: (j: JobView<R>) => void, signal?: AbortSignal): Promise<JobView<R>> {
  // Live updates over SSE (fetch, so the bearer token can be sent); polling if streaming is unavailable.
  try {
    const res = await fetch(`/api/v1/events?job=${jobId}`, { headers: { Authorization: `Bearer ${localStorage.getItem("up_token")}` }, signal });
    if (res.ok && res.body) {
      let last: JobView<R> | null = null;
      for await (const msg of sse(res.body)) {
        if (msg.event !== "job") continue;
        last = JSON.parse(msg.data) as JobView<R>;
        onUpdate?.(last);
        if (last.terminal) return last;
      }
    }
  } catch (e) {
    if (signal?.aborted) throw e;
  }
  const deadline = Date.now() + 5 * 60_000;
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const job = await api<JobView<R>>(`/jobs/${jobId}`);
    onUpdate?.(job);
    if (job.terminal) return job;
    await new Promise((r) => setTimeout(r, 700));
  }
  throw new ApiError(504, "The job is taking longer than expected. It will keep running; check back shortly.");
}

/** Starts a job (the POST must return `{ job_id }` with 202) and resolves with its result when it succeeds. */
export async function runJob<R = Record<string, unknown>>(
  path: string,
  onUpdate?: (j: JobView<R>) => void,
  init?: { headers?: Record<string, string>; signal?: AbortSignal },
): Promise<R> {
  const started = await api<{ job_id: string }>(path, { method: "POST", headers: init?.headers });
  const job = await follow<R>(started.job_id, onUpdate, init?.signal);
  if (job.status !== "succeeded") throw new ApiError(job.status === "failed" ? 409 : 500, job.error ?? `The job ${job.status}`);
  return job.result as R;
}
