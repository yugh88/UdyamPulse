import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BandChip, Card, ErrorNote } from "../components/ui";
import { api, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { inr } from "../lib/format";

interface AppRow {
  id: number;
  factory_id: string;
  name: string;
  sector: string;
  cluster: string;
  state: string;
  requested_amount: number;
  score: number | null;
  band: string | null;
  channel: string;
  review_requested: boolean;
}

export default function Console() {
  const { session } = useAuth();
  const [apps, setApps] = useState<AppRow[]>([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<AppRow[]>("/applications").then(setApps).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (q.length < 2) return setResults([]);
    const t = setTimeout(() => api(`/factories?q=${encodeURIComponent(q)}&limit=6`).then(setResults), 250);
    return () => clearTimeout(t);
  }, [q]);

  async function create(factory_id: string) {
    try {
      await post("/applications", { factory_id, channel: "rm" });
      setQ("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Applications</h1>
          <p className="text-sm text-muted">Underwrite MSME manufacturers on consented GST, e-way bill, bank, power and ERP data.</p>
        </div>
      </div>
      <ErrorNote error={error} />
      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              {["ID", "Factory", "Sector · cluster", "Requested", "State", "Score", "Band", "Channel"].map((h) => (
                <th key={h} className="label pb-2 pr-3">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {apps.map((a) => (
              <tr key={a.id} className="border-b border-line/60 last:border-0 hover:bg-surface">
                <td className="py-2.5 pr-3 font-mono text-xs text-muted">#{a.id}</td>
                <td className="pr-3">
                  <Link to={`/console/${a.id}`} className="font-semibold text-navy hover:text-magenta">
                    {a.name}
                  </Link>
                  {a.factory_id === "UP-F0001" && <span className="ml-2 rounded bg-magenta/10 px-1.5 text-[10px] font-bold text-magenta">DEMO</span>}
                  {a.review_requested && <span className="ml-2 rounded bg-amber/20 px-1.5 text-[10px] font-bold text-navy">REVIEW REQUESTED</span>}
                </td>
                <td className="pr-3 text-muted">
                  {a.sector} · {a.cluster}
                </td>
                <td className="pr-3 tabular-nums">{inr(a.requested_amount)}</td>
                <td className="pr-3 text-xs font-semibold">{a.state.replace("_", " ")}</td>
                <td className="pr-3 font-semibold tabular-nums">{a.score ?? "–"}</td>
                <td className="pr-3">
                  <BandChip band={a.band} />
                </td>
                <td className="text-xs text-muted">{a.channel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {session?.role === "rm" && (
        <Card title="New application">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search a factory by name or ID (e.g. Ceramics, UP-F0042)"
            className="w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-violet"
          />
          <ul className="mt-2 divide-y divide-line">
            {results.map((f) => (
              <li key={f.factory_id} className="flex items-center justify-between py-2 text-sm">
                <span>
                  <b>{f.name}</b> <span className="text-muted">· {f.sector_label} · {f.cluster} · {f.udyam_category} · {f.turnover_band}</span>
                </span>
                <button className="btn-ghost" onClick={() => create(f.factory_id)}>
                  Create for {inr(f.loan_requested_inr)}
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
