import { AlertTriangle, CheckCircle2, CircleHelp, Plane } from "lucide-react";
import { causeName, fmt, t, type Key, type Lang } from "../lib/i18n";
import type { Evidence } from "../types/api";

const LEVEL_ICON = { high: CheckCircle2, medium: AlertTriangle, low: CircleHelp };
const RING = { high: "var(--leaf-600)", medium: "var(--amber-600)", low: "var(--grey-500)" };

interface Props { evidence: Evidence; zoneAcres: number | null; fieldAcres: number; lang?: Lang; onBook?: () => void }

/** The decision, why, and what happens next. Wording is always "suspected", never a certain diagnosis. */
export default function EvidenceCard({ evidence: ev, zoneAcres, fieldAcres, lang = "hi", onBook }: Props) {
  const pct = Math.round(ev.confidence * 100);
  const Icon = LEVEL_ICON[ev.level];
  const maxShare = Math.max(...ev.signals.map((s) => s.share), 0.01);

  return (
    <section className="panel stack" aria-labelledby="ev-title">
      <div className="row" style={{ alignItems: "center", gap: "var(--s-300)" }}>
        <div className="ring" style={{ "--p": pct, "--ring": RING[ev.level] } as React.CSSProperties}
          role="img" aria-label={`${t("ev.confidence", {}, lang)} ${pct}%`}>
          <div><span className="num">{pct}%</span></div>
        </div>
        <div className="stack" style={{ gap: "var(--s-75)", flex: 1, minWidth: 180 }}>
          <h2 id="ev-title" className="heading-5">{t("ev.suspected", { cause: causeName(ev.cause, lang) }, lang)}</h2>
          <span className={`chip level-${ev.level}`}><Icon size={14} aria-hidden="true" />{t(`ev.level.${ev.level}` as Key, {}, lang)}</span>
          {zoneAcres !== null && (
            <p className="body-6 num">{t("ev.zone", { zone: fmt(zoneAcres, 2), field: fmt(fieldAcres, 2) }, lang)}</p>
          )}
        </div>
      </div>

      <div className="bars" role="list" aria-label="Signals">
        {ev.signals.map((s) => (
          <div key={s.name} role="listitem" style={{ display: "contents" }}>
            <span className="body-6">{t(`ev.signal.${s.name}` as Key, {}, lang)}</span>
            <span className="bar"><i className={s.supports === ev.cause ? "" : "other"}
              style={{ transform: `scaleX(${s.share / maxShare})` }} /></span>
            <span className="caption-3 num">{Math.round(s.share * 100)}%</span>
          </div>
        ))}
      </div>

      {ev.low_spot_warning && <p className="notice notice-warn body-6">{t("ev.low_spot", {}, lang)}</p>}

      <div className="stack" style={{ gap: "var(--s-75)" }}>
        <p className="title-3">{t(`ev.action.${ev.action}` as Key, {}, lang)}</p>
        {ev.plan?.spray && (
          <p className="body-6 num">{ev.plan.spray.product}: {fmt(ev.plan.spray.quantity)} {ev.plan.spray.unit}</p>
        )}
        {ev.plan && <p className="caption-5">{t("ev.source", { source: ev.plan.source }, lang)}</p>}
      </div>

      {onBook && (ev.action === "advise_spray" || ev.action === "didi_verify") && (
        <button type="button" className="btn btn-primary btn-big" onClick={onBook}>
          <Plane aria-hidden="true" /> {t("ev.book_didi", {}, lang)}
        </button>
      )}
    </section>
  );
}
