import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Delta } from "../components/change";
import { ProvenanceBadge } from "../components/provenance";
import {
  Badge,
  BandPill,
  Card,
  DataTable,
  ErrorState,
  PageHeader,
  SeverityPill,
  Skeleton,
  Stat,
  TabCount,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Tooltip,
  useUrlTab,
} from "../components/ui";
import { Heatmap, type CellFilter } from "../features/cockpit/Heatmap";
import { MigrationMatrix } from "../features/cockpit/MigrationMatrix";
import { api } from "../lib/api";
import { crore, inr } from "../lib/format";
import { monthLabel } from "../lib/time";
import type { Migration, Portfolio as PortfolioData, PortfolioAccount } from "../lib/types";

const TABS = ["overview", "movement", "exposure"] as const;
const SEV_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 60},${18 - ((v - min) / span) * 16}`).join(" ");
  const down = values[values.length - 1] < values[0];
  return (
    <svg width={60} height={20} viewBox="0 0 60 20" role="img" aria-label={`Score over ${values.length} months: ${values[0]} to ${values[values.length - 1]}`}>
      <polyline points={pts} fill="none" stroke={down ? "var(--danger)" : "var(--success)"} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function Portfolio() {
  const nav = useNavigate();
  const [tab, setTab] = useUrlTab(TABS, "overview");
  const [cell, setCell] = useState<CellFilter | null>(null);
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: () => api<PortfolioData>("/portfolio") });
  const migration = useQuery({ queryKey: ["migration"], queryFn: () => api<Migration>("/portfolio/migration"), enabled: tab === "movement" || tab === "overview" });

  const accounts = useMemo(() => {
    const rows = portfolio.data?.accounts;
    return rows && cell ? rows.filter((r) => r.cluster === cell.cluster && r.sector === cell.sector) : rows;
  }, [portfolio.data, cell]);

  const columns = useMemo<ColumnDef<PortfolioAccount>[]>(
    () => [
      { accessorKey: "name", header: "Factory", meta: { label: "Factory" }, cell: ({ getValue }) => <span className="font-semibold text-fg">{getValue<string>()}</span> },
      { accessorKey: "cluster", header: "Cluster", meta: { label: "Cluster" } },
      { accessorKey: "sector", header: "Sector", meta: { label: "Sector" } },
      { accessorKey: "exposure", header: "Exposure", meta: { label: "Exposure (₹)", align: "right" }, cell: ({ getValue }) => inr(getValue<number>()) },
      { accessorKey: "score", header: "Score", meta: { label: "Score", align: "right" }, cell: ({ getValue }) => <span className="font-bold">{getValue<number>()}</span> },
      {
        accessorKey: "trend_3m",
        header: "3-month change",
        meta: { label: "3-month change", align: "right" },
        cell: ({ getValue }) => <Delta value={getValue<number>()} goodWhenUp size="sm" />,
      },
      {
        id: "trend",
        header: "6 months",
        meta: { label: "6-month trend", csv: (a) => a.sparkline.join(" ") },
        enableSorting: false,
        cell: ({ row }) => <Sparkline values={row.original.sparkline} />,
      },
      { accessorKey: "band", header: "Band", meta: { label: "Band" }, cell: ({ row }) => <BandPill band={row.original.band} /> },
      {
        id: "alerts",
        accessorFn: (a) => SEV_RANK[a.max_severity ?? ""] ?? 0,
        header: "Alert",
        meta: { label: "Highest open alert", csv: (a) => a.max_severity ?? "" },
        cell: ({ row }) => (row.original.max_severity ? <SeverityPill severity={row.original.max_severity} /> : <span className="text-fg-muted">–</span>),
      },
      {
        accessorKey: "consent_active",
        header: "Consent",
        meta: { label: "Consent", csv: (a) => (a.consent_active ? "active" : "revoked") },
        cell: ({ getValue }) =>
          getValue<boolean>() ? (
            <Badge tone="success" icon={<ShieldCheck className="h-3 w-3" aria-hidden />}>
              Active
            </Badge>
          ) : (
            <Badge tone="danger" icon={<ShieldOff className="h-3 w-3" aria-hidden />}>
              Revoked
            </Badge>
          ),
      },
    ],
    [],
  );

  if (portfolio.isError) return <ErrorState error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  const k = portfolio.data?.kpis;
  const flagged = portfolio.data ? portfolio.data.accounts.filter((a) => a.max_severity === "high" || a.max_severity === "medium") : [];
  const openAlerts = k ? k.alerts_by_severity.high + k.alerts_by_severity.medium + k.alerts_by_severity.low : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portfolio"
        aside={<ProvenanceBadge value="Synthetic" />}
        description={
          portfolio.data
            ? `${portfolio.data.kpis.accounts} monitored accounts · data through ${monthLabel(portfolio.data.data_month)}`
            : "The monitored book, by cluster, sector and band."
        }
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Portfolio views">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="movement">
            Band movement
            <TabCount value={migration.data ? migration.data.downgrades + migration.data.upgrades : null} />
          </TabsTrigger>
          <TabsTrigger value="exposure">
            Exposure
            <TabCount value={k?.accounts ?? null} />
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Monitored accounts" value={k?.accounts ?? "–"} loading={portfolio.isLoading} />
            <Stat label="Total exposure" value={k ? `₹${crore(k.exposure)}` : "–"} loading={portfolio.isLoading} />
            <Stat label="Average score" value={k?.avg_score ?? "–"} sub="out of 900" loading={portfolio.isLoading} />
            <Stat
              label="Open alerts"
              value={openAlerts ?? "–"}
              loading={portfolio.isLoading}
              sub={
                k && (
                  <Tooltip content={`${k.slippage_formula}. Estimated slippage avoided: ${inr(k.expected_slippage_avoided)}.`}>
                    <span tabIndex={0} className="underline decoration-dotted underline-offset-2">
                      {k.alerts_by_severity.high} high · {flagged.length} accounts flagged
                    </span>
                  </Tooltip>
                )
              }
            />
          </div>
          <Card title="Cluster × sector" description="Average health score of monitored accounts. Select a cell to see those accounts under Exposure.">
            {portfolio.data ? (
              <Heatmap
                cells={portfolio.data.heatmap}
                selected={cell}
                onSelect={(c) => {
                  setCell(c);
                  if (c) setTab("exposure");
                }}
              />
            ) : (
              <Skeleton className="h-72" />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="movement">
          <Card title="Band movement" description="Accounts that changed band since last month">
            {migration.isError ? (
              <ErrorState error={migration.error} onRetry={() => migration.refetch()} />
            ) : migration.data ? (
              <MigrationMatrix data={migration.data} />
            ) : (
              <Skeleton className="h-72" />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="exposure">
          <Card title="Monitored accounts" description={cell ? `Filtered to ${cell.cluster} · ${cell.sector}` : "Every disbursed account under early-warning monitoring"}>
            {cell && (
              <button type="button" onClick={() => setCell(null)} className="mb-3 text-13 font-semibold text-info hover:underline">
                Clear filter
              </button>
            )}
            <DataTable
              caption="Monitored accounts"
              data={accounts}
              columns={columns}
              getRowId={(a) => String(a.application_id)}
              loading={portfolio.isLoading}
              onRowClick={(a) => nav(`/console/${a.application_id}`)}
              rowLabel={(a) => `Open account ${a.name}`}
              searchPlaceholder="Search accounts"
              csvName="monitored_accounts"
              maxHeight={640}
              emptyTitle="No monitored accounts"
              emptyDescription="Accounts appear here after disbursal."
            />
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
