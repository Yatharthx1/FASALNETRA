import { useCallback, useEffect, useState } from "react";
import { ExternalLink, Phone, PhoneCall, Plus, RotateCcw, Volume2 } from "lucide-react";
import EvidenceCard from "../components/EvidenceCard";
import FieldMap from "../components/FieldMap";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api, eventsSocket } from "../lib/api";
import { causeName, fmt, speak, t, type Lang } from "../lib/i18n";
import type { AppEvent, Case, IvrPrompt } from "../types/api";

const LANG: Lang = "en";   // dashboard is for judges; farmer and Didi screens are Hindi
const DEMO_TRAPS = [3, 12, 5, 2];
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", ""];

function eventLine(e: AppEvent): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.type) {
    case "case_created": return `Case #${e.case_id}: satellite flagged ${p.flagged_acres} acre (scene ${p.scene})`;
    case "call_placed": return `${p.kind === "result" ? "Result" : "Warning"} call ${p.simulated ? "(simulated)" : "placed"}`;
    case "key_pressed": return `Farmer pressed ${p.digit} on ${p.step}`;
    case "answer_saved": return `Answer saved: ${Object.entries(p.answers as object).map(([k, v]) => `${k}=${v ? "yes" : "no"}`).join(", ")}`;
    case "sms_sent": return `SMS ${p.kind === "dose" ? "with dose" : "with link"} ${p.simulated ? "(simulated)" : "sent"}`;
    case "traps_counted": return `Trap counts ${(p.counts as number[]).join(", ")}`;
    case "photo_received": return `Photo ${p.kind} spot ${Number(p.spot) + 1}: ${p.label} ${Math.round(Number(p.confidence) * 100)}%${p.retake ? ` (retake: ${p.retake})` : ""}`;
    case "zone_mapped": return `Zone mapped from walk: ${p.acres} acre`;
    case "evidence_ready": return `Evidence: ${causeName(String(p.cause), LANG)} ${Math.round(Number(p.confidence) * 100)}% ${p.level} → ${p.action}`;
    case "neighbours_warned": return `${p.count} neighbouring soybean fields warned`;
    case "didi_booked": return `Drone Didi booked (${p.mode}), ${p.minutes} min flight, best ${String(p.best ?? "-").slice(11, 16)}`;
    case "didi_complete": return `Spray done. ${p.acres_not_sprayed} acre not sprayed, ${p.chemical_saved} ${p.unit ?? ""} saved`;
    case "human_requested": return "Farmer asked for a human expert";
    case "booking_skipped": return `Drone Didi not booked: ${p.reason}`;
    case "followup_recorded": return `Follow-up answer: ${String(p.feedback).replace(/_/g, " ")}`;
    default: return e.type.replace(/_/g, " ");
  }
}

export default function Dashboard() {
  const fieldQ = useAsync(() => api.field(), []);
  const riskQ = useAsync(() => api.risk(), []);
  const scanQ = useAsync(() => api.scan(), []);
  const [kase, setKase] = useState<Case | null>(null);
  const [events, setEvents] = useState<AppEvent[]>([]);
  const [prompt, setPrompt] = useState<IvrPrompt | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshCase = useCallback(async (id: number) => setKase(await api.getCase(id)), []);

  const takeLink = useCallback((e: AppEvent) => {
    if (e.type === "sms_sent" && typeof e.payload.url === "string") {
      const u = new URL(e.payload.url);
      setLink(`${location.origin}${u.pathname}${u.search}`);   // same origin as the dashboard (proxy)
    }
  }, []);

  useEffect(() => {
    // After a page reload, pick up the latest case and its link from the event log.
    api.events().then((list) => {
      setEvents(list);
      const last = [...list].reverse().find((e) => e.type === "case_created");
      if (last?.case_id) {
        refreshCase(last.case_id).catch(() => undefined);
        list.filter((e) => e.case_id === last.case_id).forEach(takeLink);
      }
    }).catch(() => undefined);
    return eventsSocket((e) => {
      setEvents((list) => [...list.slice(-199), e]);
      takeLink(e);
      if (e.case_id && ["photo_received", "zone_mapped", "evidence_ready", "didi_booked", "traps_counted"].includes(e.type)) {
        refreshCase(e.case_id).catch(() => undefined);
      }
      if (e.type === "demo_reset") { setKase(null); setPrompt(null); setLink(null); setEvents([e]); }
    });
  }, [refreshCase, takeLink]);

  async function run(fn: () => Promise<void>) {
    setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); }
  }

  const press = (digit: string) => prompt && !prompt.is_completed && run(async () => {
    const next = await api.keypad(prompt.phone, digit);
    setPrompt(next);
    speak(next.prompt_text);
  });

  const today = riskQ.data?.days[0];
  const field = fieldQ.data;

  return (
    <main className="dash">
      <header className="dash-top">
        <h1 className="heading-5">{t("app.name", {}, LANG)}</h1>
        {field && (
          <span className="body-6">{field.farmer.name} · Khasra {field.khasra}, {field.farmer.village} · soybean ·{" "}
            <span className="num">{t("dash.crop_age", { days: today?.das ?? "-" }, LANG)}</span></span>
        )}
        {today && <span className={`chip band-${today.band}`}>{causeName(today.top, LANG)} <span className="num">{Math.round(today.score)}</span></span>}
        {riskQ.data && (
          <figure className="row" style={{ margin: 0 }} aria-label={t("dash.risk", {}, LANG)}>
            <div className="spark" aria-hidden="true">
              {riskQ.data.days.map((d) => <i key={d.date} className={d.band} style={{ height: `${Math.max(8, d.score)}%` }} title={`${d.date} ${d.score}`} />)}
            </div>
            <figcaption className="caption-5">{t("dash.risk", {}, LANG)} ({riskQ.data.mode}, rule {riskQ.data.rule_status})</figcaption>
          </figure>
        )}
        <span style={{ flex: 1 }} />
        <a className="btn" href="/didi" target="_blank" rel="noreferrer">Drone Didi <ExternalLink size={16} aria-hidden="true" /></a>
        <button type="button" className="btn" onClick={() => run(async () => { await api.reset(); })}>
          <RotateCcw size={16} aria-hidden="true" /> {t("dash.reset", {}, LANG)}
        </button>
      </header>

      <section className="dash-map" aria-label="Field map">
        {field ? (
          <FieldMap field={field.geometry} cells={scanQ.data?.cells} targets={kase?.target_cells} zone={kase?.zone}
            trail={kase?.walk_trail} label="Hero field with Sentinel-2 grid" />
        ) : <Skeleton height={480} />}
      </section>

      <aside className="dash-side">
        {(fieldQ.error || riskQ.error || scanQ.error) && <ErrorNotice error={(fieldQ.error || riskQ.error || scanQ.error)!} />}
        {error && <ErrorNotice error={error} />}
        {scanQ.data && (
          <p className="caption-5 num">Sentinel-2 {scanQ.data.scene_date}: {scanQ.data.summary.cells_flagged}/{scanQ.data.summary.cells_in_field} cells flagged,
            {" "}{scanQ.data.summary.flagged_acres} acre, {scanQ.data.summary.pattern}</p>
        )}

        <section className="panel stack">
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={() => run(async () => { const c = await api.createCase(); setKase(c); setPrompt(null); setLink(null); })}>
              <Plus size={16} aria-hidden="true" /> {t("dash.new_case", {}, LANG)}
            </button>
            <button type="button" className="btn" disabled={!kase} onClick={() => run(async () => {
              const r = await api.warningCall(kase!.id); setPrompt(r.first_prompt); speak(r.first_prompt.prompt_text); })}>
              <PhoneCall size={16} aria-hidden="true" /> {t("dash.warning_call", {}, LANG)}
            </button>
            <button type="button" className="btn" disabled={!kase} onClick={() => run(async () => { await api.traps(kase!.id, DEMO_TRAPS); })}>
              {t("dash.traps", { counts: DEMO_TRAPS.join("/") }, LANG)}
            </button>
            <button type="button" className="btn" disabled={!kase} onClick={() => run(async () => { setKase(await api.evidence(kase!.id)); })}>
              {t("dash.build_evidence", {}, LANG)}
            </button>
            <button type="button" className="btn" disabled={!kase?.evidence} onClick={() => run(async () => {
              const r = await api.resultCall(kase!.id); setPrompt(r.first_prompt); speak(r.first_prompt.prompt_text); })}>
              <Phone size={16} aria-hidden="true" /> {t("dash.result_call", {}, LANG)}
            </button>
          </div>
          {!kase && <p className="body-6 muted">{t("dash.no_case", {}, LANG)}</p>}
          {link && <a className="btn" href={link} target="_blank" rel="noreferrer"><ExternalLink size={16} aria-hidden="true" /> {t("dash.open_walk", {}, LANG)}</a>}
        </section>

        {prompt && (
          <section className="panel stack" aria-labelledby="phone-title">
            <div className="row spread">
              <h2 id="phone-title" className="title-3">{t("dash.keypad", {}, LANG)} · <span className="caption-5">{prompt.current_step}</span></h2>
              <button type="button" className="btn btn-icon" aria-label="Play prompt" onClick={() => speak(prompt.prompt_text)}><Volume2 size={18} /></button>
            </div>
            <p className="ivr-say" aria-live="polite">{prompt.prompt_text}</p>
            <div className="keypad">
              {KEYS.map((k, i) => k ? (
                <button key={k} type="button" className={`btn num ${prompt.valid_digits.includes(k) ? "btn-primary" : ""}`} disabled={prompt.is_completed}
                  onClick={() => press(k)}>{k}</button>
              ) : <span key={`gap${i}`} />)}
            </div>
          </section>
        )}

        {kase?.evidence && field && (
          <EvidenceCard evidence={kase.evidence} zoneAcres={kase.zone_acres} fieldAcres={field.area_acres} lang={LANG}
            onBook={() => run(async () => { await api.bookDidi(kase.id); })} />
        )}
        {kase?.evidence?.savings && (
          <p className="notice notice-ok body-6 num">
            {fmt(kase.evidence.savings.acres_not_sprayed, 2)} acre not sprayed · {fmt(kase.evidence.savings.chemical_saved)} {kase.evidence.savings.unit} chemical saved
          </p>
        )}

        <section className="panel stack" aria-labelledby="feed-title">
          <h2 id="feed-title" className="title-3">{t("dash.feed", {}, LANG)}</h2>
          <ol className="feed" aria-live="polite">
            {[...events].reverse().slice(0, 40).map((e, i) => (
              <li key={e.id ?? `live-${i}`}>
                <span className="caption-5 num">{e.ts ? new Date(e.ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : ""}</span>
                <span className="body-6">{eventLine(e)}</span>
              </li>
            ))}
          </ol>
        </section>
      </aside>
    </main>
  );
}
