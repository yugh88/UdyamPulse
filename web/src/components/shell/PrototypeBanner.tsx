import { FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import "../../i18n"; // the banner is on every screen, so it must not wait for the MSME app to set up i18n

/** Always visible: this is a prototype on synthetic data, and nothing on screen is a lending decision. */
export function PrototypeBanner() {
  const { t } = useTranslation();
  return (
    <div role="note" className="flex items-center justify-center gap-1.5 border-b border-edge bg-panel-2 px-3 py-1 text-xs text-fg-muted">
      <FlaskConical className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>{t("banner.prototype")}</span>
    </div>
  );
}
