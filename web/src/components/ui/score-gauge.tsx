import { BAND_LABEL, BAND_VAR, type Band } from "../../lib/format";

const MIN = 300;
const MAX = 900;
const R = 80;
const CX = 110;
const CY = 104;
const ZONES: { from: number; to: number; band: Band }[] = [
  { from: 300, to: 550, band: "HIGH_RISK" },
  { from: 550, to: 650, band: "WATCH" },
  { from: 650, to: 900, band: "APPROVE" },
];

const frac = (v: number) => (Math.min(MAX, Math.max(MIN, v)) - MIN) / (MAX - MIN);

function point(v: number, r: number): [number, number] {
  const a = Math.PI * (1 - frac(v));
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
}

function arc(from: number, to: number): string {
  const [x1, y1] = point(from, R);
  const [x2, y2] = point(to, R);
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${R} ${R} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

/**
 * Factory Health Score gauge (300–900): a soft arc with the three policy band zones, a needle
 * that eases to the score, and the number in the centre. The band is also given as text.
 */
export function ScoreGauge({
  score,
  band,
  size = 240,
  caption = "Factory Health Score",
}: {
  score: number | null | undefined;
  band?: string | null;
  size?: number;
  caption?: string;
}) {
  const has = score != null;
  const angle = has ? -90 + 180 * frac(score) : -90;
  const label = has ? `${caption} ${score} out of 900${band ? `, band ${BAND_LABEL[band as Band] ?? band}` : ""}` : `${caption}: not scored yet`;
  return (
    <figure className="flex flex-col items-center" role="img" aria-label={label}>
      <svg viewBox="0 0 220 128" width={size} className="max-w-full">
        {ZONES.map((z) => (
          <path
            key={z.band}
            d={arc(z.from + 3, z.to - 3)}
            stroke={BAND_VAR[z.band]}
            strokeOpacity={has && band === z.band ? 0.95 : 0.3}
            strokeWidth={12}
            strokeLinecap="round"
            fill="none"
          />
        ))}
        {[300, 550, 650, 900].map((t) => {
          const [x, y] = point(t, R + 17);
          return (
            <text key={t} x={x} y={y + 3} fontSize={9} textAnchor="middle" fill="var(--text-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
              {t}
            </text>
          );
        })}
        {has && (
          <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: `${CX}px ${CY}px`, transition: "transform 600ms cubic-bezier(.2,.8,.2,1)" }}>
            <line x1={CX} y1={CY - 46} x2={CX} y2={CY - 70} stroke="var(--text)" strokeWidth={3} strokeLinecap="round" />
          </g>
        )}
        <text x={CX} y={CY - 4} fontSize={34} fontWeight={650} textAnchor="middle" fill="var(--text)" style={{ fontVariantNumeric: "tabular-nums" }}>
          {has ? score : "–"}
        </text>
        <text x={CX} y={CY + 14} fontSize={10} textAnchor="middle" fill="var(--text-muted)">
          {has ? "of 900" : "not scored"}
        </text>
      </svg>
      <figcaption className="text-xs text-fg-muted">{caption} (300–900)</figcaption>
    </figure>
  );
}
