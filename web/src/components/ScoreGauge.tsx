import { BAND_STYLE } from "../lib/format";

const MIN = 300;
const MAX = 900;
const BANDS = [
  { from: 300, to: 549, color: BAND_STYLE.HIGH_RISK.color },
  { from: 550, to: 649, color: BAND_STYLE.WATCH.color },
  { from: 650, to: 900, color: BAND_STYLE.APPROVE.color },
];

function polar(v: number, r: number) {
  const a = Math.PI * (1 - (v - MIN) / (MAX - MIN));
  return [100 + r * Math.cos(a), 100 - r * Math.sin(a)];
}

function arc(from: number, to: number, r: number) {
  const [x1, y1] = polar(from, r);
  const [x2, y2] = polar(to, r);
  return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
}

/** Semicircle 300–900 gauge with the three policy bands and a needle. */
export function ScoreGauge({ score, band, size = 220 }: { score: number | null; band?: string | null; size?: number }) {
  const [nx, ny] = score != null ? polar(score, 58) : [100, 100];
  return (
    <figure className="flex flex-col items-center" role="img" aria-label={score != null ? `Factory Health Score ${score}, band ${band}` : "Not scored"}>
      <svg viewBox="-16 0 232 136" width={size}>
        {BANDS.map((b) => (
          <path key={b.from} d={arc(b.from, b.to + (b.to === 900 ? 0 : 1), 80)} stroke={b.color} strokeWidth={14} fill="none" opacity={0.9} />
        ))}
        {[300, 550, 650, 900].map((t) => {
          const [x, y] = polar(t, 98);
          return (
            <text key={t} x={x} y={y + 3} fontSize={8} textAnchor="middle" fill="#6b7088">
              {t}
            </text>
          );
        })}
        {score != null && (
          <>
            <line x1={100} y1={100} x2={nx} y2={ny} stroke="#0B1033" strokeWidth={3} strokeLinecap="round" />
            <circle cx={100} cy={100} r={5} fill="#0B1033" />
          </>
        )}
        <text x={100} y={130} fontSize={24} fontWeight={700} textAnchor="middle" fill="#0B1033">
          {score ?? "—"}
        </text>
      </svg>
      <figcaption className="text-xs text-muted">Factory Health Score (300–900)</figcaption>
    </figure>
  );
}
