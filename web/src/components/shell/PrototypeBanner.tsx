import { FlaskConical, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import "../../i18n"; // the chip is on every screen, so it must not wait for the MSME app to set up i18n
import { Tooltip } from "../ui";

/** Always visible in the top bar: this is a prototype on synthetic data. The full sentence is in the tooltip. */
export function PrototypeChip() {
  const { t } = useTranslation();
  return (
    <Tooltip content={t("banner.prototype")}>
      <span tabIndex={0} className="hidden h-9 items-center gap-1.5 rounded-full border border-edge-2 bg-panel px-3.5 text-13 font-medium text-fg-muted sm:inline-flex">
        <FlaskConical className="h-4 w-4 shrink-0" aria-hidden />
        {t("banner.chip")}
      </span>
    </Tooltip>
  );
}

const KEY = "up_notice_dismissed";
function dismissed(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/** Shown once, on the first visit: what this prototype is and is not. Dismissed for good with one click. */
export function FirstVisitNotice() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(() => !dismissed());
  if (!open) return null;
  return (
    <div role="note" className="flex items-center justify-center gap-3 border-b border-edge bg-panel-2 px-4 py-1.5 text-13 text-fg-muted sm:py-2">
      <FlaskConical className="h-4 w-4 shrink-0" aria-hidden />
      {/* One line on a phone: the short label, with the full sentence for screen readers. */}
      <span className="min-w-0 truncate sm:hidden">
        <span aria-hidden>{t("banner.chip")}</span>
        <span className="sr-only">
          {t("banner.prototype")} {t("banner.roles")}
        </span>
      </span>
      <span className="hidden sm:inline">
        {t("banner.prototype")} · {t("banner.roles")}
      </span>
      <button
        type="button"
        onClick={() => {
          try {
            localStorage.setItem(KEY, "1");
          } catch {
            /* private mode: hide for this visit only */
          }
          setOpen(false);
        }}
        className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 font-medium whitespace-nowrap text-fg hover:bg-panel"
      >
        <X className="h-3.5 w-3.5" aria-hidden />
        {t("banner.dismiss")}
      </button>
    </div>
  );
}

/** The login page has no top bar, so it shows the full sentence as a slim strip. */
export function PrototypeBanner() {
  const { t } = useTranslation();
  return (
    <div role="note" className="flex items-center justify-center gap-1.5 border-b border-edge bg-panel-2 px-3 py-1.5 text-xs text-fg-muted">
      <FlaskConical className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>{t("banner.prototype")}</span>
    </div>
  );
}
