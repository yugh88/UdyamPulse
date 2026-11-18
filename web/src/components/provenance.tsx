import { FlaskConical, Globe } from "lucide-react";
import { Badge } from "./ui";

export type Provenance = "Real public data" | "Synthetic (calibrated)" | "Synthetic";

/** Every chart, report and model states where its data comes from. Real and synthetic are never blended. */
export function ProvenanceBadge({ value }: { value: Provenance | string }) {
  const real = value === "Real public data";
  return (
    <Badge tone={real ? "info" : "neutral"} icon={real ? <Globe className="h-3 w-3" aria-hidden /> : <FlaskConical className="h-3 w-3" aria-hidden />}>
      {value}
    </Badge>
  );
}
