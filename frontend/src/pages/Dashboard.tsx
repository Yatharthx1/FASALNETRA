import { useCallback, useEffect, useMemo, useState } from "react";
import qrcode from "qrcode-generator";
import { Camera, Check, Copy, ExternalLink, Phone, PhoneCall, PhoneIncoming, Plus, RotateCcw, Volume2, ShieldAlert, Sprout, X } from "lucide-react";
import EvidenceCard from "../components/EvidenceCard";
import FieldMap from "../components/FieldMap";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api, eventsSocket } from "../lib/api";
import { causeName, fmt, speak, t, type Lang } from "../lib/i18n";
import type { AppEvent, CameraLink, Case, IvrPrompt } from "../types/api";

const LANG: Lang = "en";   // dashboard is for judges; farmer and Didi screens are Hindi
const DEMO_TRAPS = [3, 12, 5, 2];
const LIVE_POLL_MS = 4000;
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", ""];

function eventLine(e: AppEvent): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.type) {
    case "case_created": return `Case #${e.case_id}: satellite flagged ${p.flagged_acres} acre (scene ${p.scene})`;
    case "call_placed": return p.error ? `Call failed: ${String(p.error).slice(0, 120)}`
      : `${p.kind === "result" ? "Result" : p.kind === "followup" ? "Day +5 follow-up" : p.kind === "onboarding" ? "Onboarding" : p.kind === "report" ? "Report-a-problem" : "Warning"} call ${p.simulated ? "(simulated)" : "placed"}`;
    case "key_pressed": return `Farmer pressed ${p.digit} on ${p.step}`;
    case "answer_saved": return `Answer saved: ${Object.entries(p.answers as object).map(([k, v]) => `${k}=${v ? "yes" : "no"}`).join(", ")}`;
    case "sms_failed": return "SMS failed (link below: open it on the phone)";
    case "sms_sent": return `SMS ${p.kind === "dose" ? "with dose" : "with link"} ${p.simulated ? "(simulated)" : "sent"}`;
    case "traps_counted": return `Trap counts ${(p.counts as number[]).join(", ")}`;
    case "photo_received": return `Photo ${p.kind} spot ${Number(p.spot) + 1}: ${p.label} ${Math.round(Number(p.confidence) * 100)}%${p.retake ? ` (retake: ${p.retake})` : ""}`;
    case "zone_mapped": return `Zone mapped from walk: ${p.acres} acre`;
    case "evidence_ready": return `Evidence: ${causeName(String(p.cause), LANG)} ${Math.round(Number(p.confidence) * 100)}% ${p.level} → ${p.action}`;
    case "neighbours_warned": return `${p.count} neighbouring soybean fields warned`;
    case "didi_booked": return `Drone Didi booked (${p.mode}), ${p.minutes} min flight, best ${String(p.best ?? "-").slice(11, 16)}`;
    case "didi_complete": return `Spray done. ${p.acres_not_sprayed} acre not sprayed, ${p.chemical_saved} ${p.unit ?? ""} saved`;
    case "human_requested": return "Farmer asked for a human expert";
    case "farmer_reported": return "Farmer gave a missed call and reported a problem";
    case "booking_skipped": return `Drone Didi not booked: ${p.reason}`;
    case "followup_recorded": return `Follow-up answer: ${String(p.feedback).replace(/_/g, " ")}`;
    default: return e.type.replace(/_/g, " ");
  }
}

export default function Dashboard() {
  const fieldQ = useAsync(() => api.field(), []);
  const riskQ = useAsync(() => api.risk(), []);
  const scanQ = useAsync(() => api.scan(), []);
  const combinedQ = useAsync(() => api.combinedAdvisory(), []);
  const soybeanQ = useAsync(() => api.soybeanProfile(), []);
  const [kase, setKase] = useState<Case | null>(null);
  const [events, setEvents] = useState<AppEvent[]>([]);
  const [prompt, setPrompt] = useState<IvrPrompt | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [camLink, setCamLink] = useState<CameraLink | null>(null);   // the popup: public link to copy or scan
  const [error, setError] = useState<string | null>(null);
  // farmer phone for "Get a call", remembered on this laptop between reloads
  const [callTo, setCallTo] = useState(() => { try { return localStorage.getItem("fn.callTo") ?? ""; } catch { return ""; } });
  const [calling, setCalling] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);

  const refreshCase = useCallback(async (id: number) => setKase(await api.getCase(id)), []);

  // Live hold (simulated call): the farmer stays on the line after the SMS link; each poll is one check,
  // like Twilio's /ivr/live redirect loop. New lines are spoken; the result prompt ends the hold.
  const holding = prompt?.current_step === "sms_dispatched" && !prompt.is_completed ? prompt.phone : null;
  useEffect(() => {
    if (!holding) return;
    const id = setInterval(() => {
      api.ivrPrompt(holding).then((p) => {
        if (!p.prompt_text) return;              // nothing new: keep the last line on screen
        setPrompt(p);
        speak(p.prompt_text);
      }).catch(() => undefined);
    }, LIVE_POLL_MS);
    return () => clearInterval(id);
  }, [holding]);

  const openCamLink = useCallback((caseId: number) => {
    api.cameraLink(caseId).then(setCamLink).catch((e: Error) => setError(e.message));
  }, []);

  const takeLink = useCallback((e: AppEvent, popup = true) => {
    if ((e.type === "sms_sent" || e.type === "sms_failed") && typeof e.payload.url === "string") {
      const u = new URL(e.payload.url);
      setLink(`${location.origin}${u.pathname}${u.search}`);   // same origin as the dashboard (proxy)
      if (popup && e.case_id) openCamLink(e.case_id);
    }
  }, [openCamLink]);

  useEffect(() => {
    // After a page reload, pick up the latest case and its link from the event log.
    api.events().then((list) => {
      setEvents(list);
      const last = [...list].reverse().find((e) => e.type === "case_created");
      if (last?.case_id) {
        refreshCase(last.case_id).catch(() => undefined);
        list.filter((e) => e.case_id === last.case_id).forEach((e) => takeLink(e, false));
      }
    }).catch(() => undefined);
    return eventsSocket((e) => {
      setEvents((list) => [...list.slice(-199), e]);
      takeLink(e);
      if (e.type === "case_created" && e.case_id) { refreshCase(e.case_id).catch(() => undefined); setLink(null); setCamLink(null); }
      if (e.case_id && ["photo_received", "zone_mapped", "evidence_ready", "didi_booked", "traps_counted"].includes(e.type)) {
        refreshCase(e.case_id).catch(() => undefined);
      }
      if (e.type === "demo_reset") { setKase(null); setPrompt(null); setLink(null); setCamLink(null); setEvents([e]); }
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

  async function getCall() {
    const phone = callTo.replace(/[\s-]/g, "");
    if (!phone) return;
    try { localStorage.setItem("fn.callTo", phone); } catch { /* private window: just not remembered */ }
    setCalling({ tone: "warn", text: `Calling ${phone}…` });
    try {
      const r = await api.getCall(phone);
      setCalling(r.error ? { tone: "error", text: `Twilio refused the call: ${r.error}` }
        : r.simulated ? { tone: "warn", text: "Twilio is not configured: call simulated" }
          : { tone: "ok", text: `Ringing ${r.phone} (${r.flow})` });
    } catch (e) {
      setCalling({ tone: "error", text: (e as Error).message });
    }
  }

  const today = riskQ.data?.days[0];
  const field = fieldQ.data;
  const combined = combinedQ.data;
  const soy = soybeanQ.data;

  return (
    <main className="dash">
      <header className="dash-top">
        <h1 className="heading-5">{t("app.name", {}, LANG)}</h1>
        {field && (
          <span className="body-6">{field.farmer.name} · Khasra {field.khasra}, {field.farmer.village} · soybean ·{" "}
            <span className="num">{t("dash.crop_age", { days: today?.das ?? "-" }, LANG)}</span></span>
        )}
        {soy && (
          <span className="caption-5" style={{ background: "rgba(34, 197, 94, 0.12)", color: "#166534", padding: "2px 8px", borderRadius: "12px", fontWeight: 600 }}>
            🌱 {soy.variety} · {soy.current_stage.code} ({soy.current_stage.name_hi})
          </span>
        )}
        {today && <span className={`chip band-${today.band}`}>{causeName(today.top, LANG)} <span className="num">{Math.round(today.score)}</span></span>}
        {combined && (
          <span className={`chip band-${combined.band === 'critical' || combined.band === 'high' ? 'high' : combined.band}`} title={combined.narrative.en}>
            Fused Score: <span className="num">{Math.round(combined.score)}/100</span> ({combined.band.toUpperCase()})
          </span>
        )}
        {riskQ.data && (
          <figure className="row" style={{ margin: 0 }} aria-label={t("dash.risk", {}, LANG)}>
            <div className="spark" aria-hidden="true">
              {riskQ.data.days.map((d) => <i key={d.date} className={d.band} style={{ height: `${Math.max(8, d.score)}%` }} title={`${d.date} ${d.score}`} />)}
            </div>
            <figcaption className="caption-5">{t("dash.risk", {}, LANG)} ({riskQ.data.mode}, rule {riskQ.data.rule_status})</figcaption>
          </figure>
        )}
        <span style={{ flex: 1 }} />
        <form className="get-call" onSubmit={(e) => { e.preventDefault(); void getCall(); }}>
          <label htmlFor="call-to" className="sr-only">Farmer phone</label>
          <input id="call-to" className="num" type="tel" inputMode="tel" placeholder="+91 farmer phone" required
            value={callTo} onChange={(e) => setCallTo(e.target.value)} />
          <button type="submit" className="btn btn-primary"><PhoneCall size={16} aria-hidden="true" /> Get a call</button>
        </form>
        <button type="button" className="btn" disabled={!kase} title={kase ? undefined : "Start a case first"}
          onClick={() => kase && openCamLink(kase.id)}>
          <Camera size={16} aria-hidden="true" /> Camera link
        </button>
        <a className="btn" href="/didi" target="_blank" rel="noreferrer">Drone Didi <ExternalLink size={16} aria-hidden="true" /></a>
        <button type="button" className="btn" onClick={() => run(async () => { await api.reset(); })}>
          <RotateCcw size={16} aria-hidden="true" /> {t("dash.reset", {}, LANG)}
        </button>
      </header>

      {calling && <p className={`notice notice-${calling.tone} body-6 dash-call-status`} role="status">{calling.text}</p>}
      {camLink && <LinkPopup link={camLink} onClose={() => setCamLink(null)} />}

      <section className="dash-map" aria-label="Field map">
        {field ? (
          <FieldMap field={field.geometry} cells={scanQ.data?.cells} targets={kase?.target_cells} zone={kase?.zone}
            trail={kase?.walk_trail} label="Hero field with Sentinel-2 grid" />
        ) : <Skeleton height={480} />}
      </section>

      <aside className="dash-side">
        {(fieldQ.error || riskQ.error || scanQ.error || combinedQ.error || soybeanQ.error) && (
          <ErrorNotice error={(fieldQ.error || riskQ.error || scanQ.error || combinedQ.error || soybeanQ.error)!} />
        )}
        {error && <ErrorNotice error={error} />}

        {/* Fused Sentinel-2 & Weather Advisory Card */}
        {combined && (
          <section className="panel stack" style={{ borderLeft: "4px solid #ef4444", background: "rgba(239, 68, 68, 0.04)" }}>
            <div className="row spread">
              <div className="row" style={{ gap: "6px" }}>
                <ShieldAlert size={18} color="#ef4444" aria-hidden="true" />
                <h2 className="title-3" style={{ margin: 0 }}>
                  Fused Sentinel + Weather Advisory
                </h2>
              </div>
              <span className={`chip band-${combined.band === 'critical' ? 'high' : combined.band}`}>
                <span className="num">{Math.round(combined.score)}</span>/100 {combined.band.toUpperCase()}
              </span>
            </div>
            <p className="body-6" style={{ margin: "2px 0", fontWeight: 600 }}>
              {combined.narrative.en}
            </p>
            <div className="row" style={{ gap: "6px", flexWrap: "wrap" }}>
              <span className="caption-5" style={{ background: "rgba(0,0,0,0.06)", padding: "2px 6px", borderRadius: "4px" }}>
                🛰️ Satellite: {combined.components.satellite.pattern} ({combined.components.satellite.flagged_acres} ac, NDRE Z={combined.components.satellite.z_ndre})
              </span>
              <span className="caption-5" style={{ background: "rgba(0,0,0,0.06)", padding: "2px 6px", borderRadius: "4px" }}>
                🌤️ Weather: Vector Risk {Math.round(combined.components.weather.vector_dispersal_factor * 100)}% ({combined.components.weather.spray_feasibility?.mean_wind_kmh ?? 5.7} km/h wind)
              </span>
              <span className="caption-5" style={{ background: "rgba(0,0,0,0.06)", padding: "2px 6px", borderRadius: "4px" }}>
                ⚡ Synergy: +{Math.round((combined.synergy_multiplier - 1.0) * 100)}% joint boost
              </span>
            </div>
            <p className="caption-5" style={{ margin: "2px 0 0", color: "#166534", fontWeight: 500 }}>
              🎯 Recommendation: {combined.action.en}
            </p>
          </section>
        )}

        {/* Soybean Phenology & ICAR-IISR Specialist Card */}
        {soy && (
          <section className="panel stack" style={{ borderLeft: "4px solid #16a34a", background: "rgba(22, 163, 74, 0.04)" }}>
            <div className="row spread">
              <div className="row" style={{ gap: "6px" }}>
                <Sprout size={18} color="#16a34a" aria-hidden="true" />
                <h2 className="title-3" style={{ margin: 0 }}>
                  Soybean Phenology & ICAR Guide
                </h2>
              </div>
              <span className="chip" style={{ background: "#dcfce7", color: "#166534", fontWeight: 600 }}>
                {soy.current_stage.code} ({soy.current_stage.water_sensitivity.toUpperCase()} SENSITIVITY)
              </span>
            </div>
            <p className="body-6" style={{ margin: "2px 0" }}>
              <strong>{soy.current_stage.name_en}</strong> ({soy.current_stage.name_hi})
              — <span className="num">{soy.current_stage.days_remaining_in_stage}</span> days left in stage.
            </p>
            {soy.foliar_nutrition && (
              <div style={{ background: "rgba(0,0,0,0.04)", padding: "4px 8px", borderRadius: "4px", margin: "2px 0" }}>
                <span className="caption-5" style={{ fontWeight: 600, color: "#15803d" }}>
                  🌿 Nutrition: {soy.foliar_nutrition.product} @ {soy.foliar_nutrition.dose}
                </span>
                <div className="caption-5" style={{ color: "#374151" }}>
                  {soy.foliar_nutrition.purpose_en}
                </div>
              </div>
            )}
            {soy.girdle_beetle_assessment && (
              <div className="row spread" style={{ fontSize: "0.8rem", marginTop: "2px" }}>
                <span>🪲 Girdle Beetle (चक्र भृंग) Risk:</span>
                <span className={`chip band-${soy.girdle_beetle_assessment.band}`}>
                  <span className="num">{Math.round(soy.girdle_beetle_assessment.score)}%</span> ({soy.girdle_beetle_assessment.band.toUpperCase()})
                </span>
              </div>
            )}
            <p className="caption-5" style={{ margin: "2px 0 0", color: "#6b7280" }}>
              💡 Pollinator Protection: Avoid chemical sprays during 10 AM - 3 PM bloom hours.
            </p>
          </section>
        )}

        {scanQ.data && (
          <p className="caption-5 num">Sentinel-2 {scanQ.data.scene_date}: {scanQ.data.summary.cells_flagged}/{scanQ.data.summary.cells_in_field} cells flagged,
            {" "}{scanQ.data.summary.flagged_acres} acre, {scanQ.data.summary.pattern}</p>
        )}

        <section className="panel stack">
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={() => run(async () => { const c = await api.createCase(); setKase(c); setPrompt(null); setLink(null); })}>
              <Plus size={16} aria-hidden="true" /> {t("dash.new_case", {}, LANG)}
            </button>
            <button type="button" className="btn" onClick={() => run(async () => {
              const { phone, callback_in_s } = await api.missedCall();
              await new Promise((r) => setTimeout(r, callback_in_s * 1000 + 500));   // free callback rings back
              const p = await api.ivrPrompt(phone); setPrompt(p); speak(p.prompt_text); })}>
              <PhoneIncoming size={16} aria-hidden="true" /> {t("dash.missed_call", {}, LANG)}
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
            <button type="button" className="btn" disabled={!kase?.evidence} onClick={() => run(async () => {
              const r = await api.followupCall(kase!.id); setPrompt(r.first_prompt); speak(r.first_prompt.prompt_text); })}>
              <Phone size={16} aria-hidden="true" /> {t("dash.followup_call", {}, LANG)}
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

/** QR code of the link as plain SVG squares: scan it with the farmer's phone camera to open the page. */
function QrCode({ text }: { text: string }) {
  const qr = useMemo(() => { const q = qrcode(0, "M"); q.addData(text); q.make(); return q; }, [text]);
  const n = qr.getModuleCount();
  const cells: string[] = [];
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) cells.push(`M${c} ${r}h1v1h-1z`);
  return (
    <svg className="link-qr" viewBox={`-2 -2 ${n + 4} ${n + 4}`} role="img" aria-label="QR code of the camera link" shapeRendering="crispEdges">
      <rect x="-2" y="-2" width={n + 4} height={n + 4} fill="#fff" />
      <path d={cells.join("")} fill="#000" />
    </svg>
  );
}

/** The farmer's camera page link: copy it, scan it, or open it on any device (phone, tablet, second laptop). */
function LinkPopup({ link, onClose }: { link: CameraLink; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const local = /\/\/(localhost|127\.0\.0\.1)[:/]/.test(link.url);
  async function copy() {
    try {
      await navigator.clipboard.writeText(link.url);
    } catch {   // http or blocked clipboard: select the text so Ctrl+C works
      const el = document.getElementById("farmer-link") as HTMLInputElement | null;
      el?.select();
      document.execCommand?.("copy");
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside className="link-popup panel" role="dialog" aria-labelledby="link-popup-title">
      <div className="row spread">
        <span id="link-popup-title" className="title-3">Farmer camera link</span>
        <button type="button" className="btn btn-icon" aria-label="Close" onClick={onClose}><X size={14} /></button>
      </div>
      <div className="link-popup-body">
        <QrCode text={link.url} />
        <p className="body-6 muted">Scan with the phone camera, or copy and send it on WhatsApp. It opens the leaf camera for this case.</p>
      </div>
      <div className="row" style={{ gap: "var(--s-75)", flexWrap: "nowrap" }}>
        <label htmlFor="farmer-link" className="sr-only">Camera link</label>
        <input id="farmer-link" className="num" readOnly value={link.url} onFocus={(e) => e.target.select()} />
        <button type="button" className="btn btn-primary" onClick={() => void copy()}>
          {copied ? <><Check size={14} aria-hidden="true" /> Copied</> : <><Copy size={14} aria-hidden="true" /> Copy</>}
        </button>
        <a className="btn btn-icon" href={link.url} target="_blank" rel="noreferrer" aria-label="Open link"><ExternalLink size={14} /></a>
      </div>
      <p role="status" className="sr-only">{copied ? "Link copied" : ""}</p>
      {link.tunnel_password && (
        <p className="notice notice-warn body-6">
          First time on a device, the page asks for a tunnel password. Enter <strong className="num">{link.tunnel_password}</strong>.
        </p>
      )}
      {local && (
        <p className="notice notice-warn body-6">This is a localhost link, so it only works on this laptop. Set PUBLIC_BASE_URL to the tunnel URL.</p>
      )}
    </aside>
  );
}
