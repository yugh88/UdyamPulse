import { BAND_LABEL, BAND_VAR, type Band } from "../../lib/format";

const MIN = 300;
const MAX = 900;
const R = 80;
const CX = 110;
const CY = 100;

const frac = (v: number) => (Math.min(MAX, Math.max(MIN, v)) - MIN) / (MAX - MIN);

function point(v: number, r = R): [number, number] {
  const a = Math.PI * (1 - frac(v));
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
}

function arc(from: number, to: number): string {
  const [x1, y1] = point(from);
  const [x2, y2] = point(to);
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${R} ${R} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

/**
 * Factory Health Score gauge (300–900): a soft track, a filled arc in the band's colour up to the score with a knob
 * at the current value, and a grey dot for the previous score when there is one. The band is also given as text.
 */
export function ScoreGauge({
  score,
  band,
  previous,
  size = 240,
  caption = "Factory Health Score",
  showCaption = false,
}: {
  score: number | null | undefined;
  band?: string | null;
  /** Last month's score: drawn as a grey dot on the track. */
  previous?: number | null;
  size?: number;
  caption?: string;
  showCaption?: boolean;
}) {
  const has = score != null;
  const colour = band && band in BAND_VAR ? BAND_VAR[band as Band] : "var(--primary)";
  const label = has
    ? `${caption} ${score} out of 900${band ? `, band ${BAND_LABEL[band as Band] ?? band}` : ""}${previous != null ? `, previous ${previous}` : ""}`
    : `${caption}: not scored yet`;
  const [kx, ky] = has ? point(score) : [0, 0];
  const [px, py] = previous != null ? point(previous) : [0, 0];
  return (
    <figure className="flex flex-col items-center" role="img" aria-label={label}>
      <svg viewBox="0 0 220 124" width={size} className="max-w-full">
        <path d={arc(MIN, MAX)} stroke="var(--surface-2)" strokeWidth={16} strokeLinecap="round" fill="none" />
        {has && score > MIN && (
          <path d={arc(MIN, score)} stroke={colour} strokeWidth={16} strokeLinecap="round" fill="none" style={{ transition: "d 600ms cubic-bezier(.2,.8,.2,1)" }} />
        )}
        {previous != null && previous !== score && <circle cx={px} cy={py} r={4.5} fill="var(--text-subtle)" stroke="var(--surface)" strokeWidth={2} />}
        {has && <circle cx={kx} cy={ky} r={8} fill="var(--surface)" stroke={colour} strokeWidth={3.5} />}
        <text x={CX} y={CY - 8} fontSize={44} fontWeight={700} textAnchor="middle" fill="var(--text)" style={{ fontVariantNumeric: "tabular-nums", letterSpacing: "-1px" }}>
          {has ? score : "–"}
        </text>
        <text x={CX} y={CY + 14} fontSize={11} textAnchor="middle" fill="var(--text-muted)">
          {has ? "out of 900" : "not scored yet"}
        </text>
      </svg>
      {showCaption && <figcaption className="text-xs text-fg-muted">{caption} (300–900)</figcaption>}
    </figure>
  );
}
