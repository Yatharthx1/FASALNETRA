import { useEffect, useState } from "react";
import { CheckCircle2, CircleHelp, Phone, Plane, Volume2 } from "lucide-react";
import FieldMap from "./FieldMap";
import { Skeleton } from "./common";
import { api } from "../lib/api";
import { causeName, fmt, speak, t, type Key } from "../lib/i18n";
import type { Case, Field, Job } from "../types/api";

const RING = { high: "var(--leaf-600)", medium: "var(--amber-600)", low: "var(--grey-500)" };
const POLL_MS = 1500;
const ddmm = (iso?: string) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "");

/** Farmer's result: what we suspect, how sure we are, and (when not sure) the offer to send Drone Didi. */
export default function FarmerResult({ kase, field, onCase }: { kase: Case; field: Field; onCase: (c: Case) => void }) {
  const [answer, setAnswer] = useState<"asked" | "yes" | "no">("asked");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ev = kase.evidence;

  useEffect(() => {
    if (ev) return;
    const id = setInterval(() => api.getCase(kase.id).then(onCase).catch(() => undefined), POLL_MS);
    return () => clearInterval(id);
  }, [ev, kase.id, onCase]);

  const sure = ev?.level === "high";
  const pest = Boolean(ev?.plan?.spray);
  const offerDidi = Boolean(ev && pest && (!sure || ev.action === "didi_verify"));
  const message = !ev ? "" :
    !pest ? t("result.no_pesticide", { cause: causeName(ev.cause) }) :
      sure ? t("result.sure", { cause: causeName(ev.cause), pct: Math.round(ev.confidence * 100), acres: fmt(kase.zone_acres ?? 0, 2) }) :
        t("result.unsure", { cause: causeName(ev.cause) });   // the percentage is shown only when we are sure

  useEffect(() => {
    if (!ev) return;
    speak(offerDidi ? `${message} ${t("result.ask_didi")}` : message);
  }, [ev, message, offerDidi]);

  async function connect() {
    setError(null);
    try {
      const j = await api.bookDidi(kase.id);
      setJob(j);
      setAnswer("yes");
      speak(t("result.didi_booked", { date: ddmm(j.schedule[0]?.date), time: j.schedule[0]?.time ?? "" }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!ev) {
    return (
      <main className="walk" aria-busy="true">
        <h1 className="heading-4">{t("result.waiting")}</h1>
        <Skeleton height={160} /><Skeleton height={120} />
      </main>
    );
  }

  const pct = Math.round(ev.confidence * 100);
  const Icon = sure ? CheckCircle2 : CircleHelp;
  return (
    <main className="walk">
      <header className="stack" style={{ gap: "var(--s-50)" }}>
        <h1 className="heading-4">{t("result.title")}</h1>
        <p className="title-2 muted">{t("walk.welcome.field", { khasra: field.khasra, village: field.farmer.village })}</p>
      </header>

      <section className="panel stack result-card" aria-labelledby="res-cause">
        <div className="row" style={{ gap: "var(--s-300)", flexWrap: "nowrap" }}>
          {sure ? (
            <div className="ring ring-big" style={{ "--p": pct, "--ring": RING[ev.level] } as React.CSSProperties}
              role="img" aria-label={`${t("ev.confidence")} ${pct}%`}>
              <div><span className="num">{pct}%</span></div>
            </div>
          ) : <Icon size={72} aria-hidden="true" style={{ color: RING[ev.level], flexShrink: 0 }} />}
          <div className="stack" style={{ gap: "var(--s-75)" }}>
            <h2 id="res-cause" className="heading-5">{t("ev.suspected", { cause: causeName(ev.cause) })}</h2>
            <span className={`chip level-${ev.level}`}><Icon size={16} aria-hidden="true" /> {t(`ev.level.${ev.level}` as Key)}</span>
          </div>
        </div>
        <p className="title-2">{message}</p>
        <button type="button" className="play" onClick={() => speak(offerDidi && answer === "asked" ? `${message} ${t("result.ask_didi")}` : message)}>
          <Volume2 aria-hidden="true" size={28} /> {t("common.play")}
        </button>
        {kase.zone && <div className="walk-map" style={{ height: 200, minHeight: 200 }}><FieldMap field={field.geometry} zone={kase.zone} label="Sick patch" /></div>}
        {sure && ev.plan?.spray && (
          <p className="body-3 num">{ev.plan.spray.product}: {fmt(ev.plan.spray.quantity)} {ev.plan.spray.unit} · {t("result.only_patch")}</p>
        )}
        {ev.plan && <p className="caption-5">{t("ev.source", { source: ev.plan.source })}</p>}
      </section>

      {error && <p className="notice notice-error" role="alert">{error}</p>}

      {offerDidi && answer === "asked" && (
        <section className="panel stack agent-ask" aria-labelledby="ask-didi">
          <p id="ask-didi" className="heading-5">{t("result.ask_didi")}</p>
          <p className="body-3 muted">{t("result.ask_didi_why")}</p>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <button type="button" className="btn btn-primary btn-big" style={{ flex: 2 }} onClick={connect}>
              <Plane aria-hidden="true" /> {t("result.yes")}
            </button>
            <button type="button" className="btn btn-big" style={{ flex: 1 }} onClick={() => { setAnswer("no"); speak(t("result.no_ok")); }}>
              {t("result.no")}
            </button>
          </div>
        </section>
      )}

      {sure && pest && ev.action === "advise_spray" && answer === "asked" && (
        <button type="button" className="btn btn-primary btn-big" onClick={connect}><Plane aria-hidden="true" /> {t("ev.book_didi")}</button>
      )}

      {answer === "yes" && job && (
        <section className="notice notice-ok stack" aria-live="polite" style={{ gap: "var(--s-75)" }}>
          <p className="heading-6"><CheckCircle2 aria-hidden="true" size={22} /> {t("result.didi_booked_title")}</p>
          <p className="body-3 num">{t("result.didi_booked", { date: ddmm(job.schedule[0]?.date), time: job.schedule[0]?.time ?? "" })}</p>
        </section>
      )}
      {answer === "no" && (
        <section className="notice notice-warn stack" aria-live="polite">
          <p className="body-3">{t("result.no_ok")}</p>
          <a className="btn" href="tel:18001801551"><Phone size={18} aria-hidden="true" /> {t("ev.action.expert_check")}</a>
        </section>
      )}
    </main>
  );
}
