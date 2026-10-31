import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft, BatteryFull, Bell, CalendarClock, ChevronRight, CloudRain, Download, Droplets, Fuel, Leaf, MapPinned, Pause,
  Plane, Play, ShieldCheck, Stethoscope, Timer, Users, Wind,
} from "lucide-react";
import FieldMap from "../components/FieldMap";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api, eventsSocket } from "../lib/api";
import { causeName, fmt, speak, t, type Key } from "../lib/i18n";
import type { DidiProfile, Job } from "../types/api";

const STATUS_CHIP: Record<Job["status"], string> = { new: "band-high", accepted: "band-watch", flying: "band-watch", done: "band-safe", declined: "level-low" };
const FLIGHT_DEMO_S = 20;        // a 4-6 minute mission replayed in 20 s on screen

export default function Didi() {
  const profileQ = useAsync(() => api.didiProfile(), []);
  const jobsQ = useAsync(() => api.jobs(), []);
  const [openId, setOpenId] = useState<number | null>(null);
  const reload = useCallback(() => { jobsQ.reload(); profileQ.reload(); }, [jobsQ.reload, profileQ.reload]);

  // New farmer request: banner + spoken alert + phone notification (jobs present at page load are not "new")
  const seen = useRef<Set<number> | null>(null);
  useEffect(() => eventsSocket((e) => {
    if (e.type === "demo_reset") { seen.current = null; setAlert(null); }   // ids restart after a reset
    if (e.type.startsWith("didi_") || e.type === "demo_reset") reload();
  }), [reload]);

  const jobs = jobsQ.data ?? [];
  const open = jobs.find((j) => j.id === openId) ?? null;

  const [alert, setAlert] = useState<Job | null>(null);
  const [canNotify, setCanNotify] = useState(() => typeof Notification !== "undefined" && Notification.permission === "granted");
  useEffect(() => {
    if (!jobsQ.data) return;
    if (seen.current === null) { seen.current = new Set(jobsQ.data.map((j) => j.id)); return; }
    const fresh = jobsQ.data.find((j) => j.status === "new" && !seen.current!.has(j.id));
    jobsQ.data.forEach((j) => seen.current!.add(j.id));
    if (!fresh) return;
    const text = t("didi.new_request", { farmer: fresh.ticket.farmer, village: fresh.ticket.village, khasra: fresh.ticket.khasra });
    setAlert(fresh);
    speak(text);
    if (canNotify) new Notification("FasalNetra", { body: text, tag: `job-${fresh.id}` });
  }, [jobsQ.data, canNotify]);

  return (
    <main className="didi">
      {profileQ.data ? <ProfileBar p={profileQ.data} /> : <Skeleton height={88} />}
      {(jobsQ.error || profileQ.error) && <ErrorNotice error={(jobsQ.error || profileQ.error)!} onRetry={reload} />}
      {!canNotify && typeof Notification !== "undefined" && Notification.permission === "default" && (
        <button type="button" className="btn" onClick={() => Notification.requestPermission().then((p) => setCanNotify(p === "granted"))}>
          <Bell size={18} aria-hidden="true" /> {t("didi.notify_on")}
        </button>
      )}
      {alert && (
        <section className="notice notice-ok row spread" role="alert">
          <p className="heading-6"><Bell size={20} aria-hidden="true" /> {t("didi.new_request", { farmer: alert.ticket.farmer, village: alert.ticket.village, khasra: alert.ticket.khasra })}</p>
          <button type="button" className="btn btn-primary" onClick={() => { setOpenId(alert.id); setAlert(null); }}>{t("didi.open_request")}</button>
        </section>
      )}

      {open ? (
        <TicketDetail key={open.id} job={open} onBack={() => setOpenId(null)} onChange={reload} />
      ) : (
        <section className="stack" aria-labelledby="tickets">
          <div className="row spread">
            <h2 id="tickets" className="heading-5">{t("didi.tickets", { n: jobs.filter((j) => j.status !== "done" && j.status !== "declined").length })}</h2>
            <span className="body-6 muted">{t("didi.sorted")}</span>
          </div>
          {jobsQ.loading && !jobsQ.data && <><Skeleton height={110} /><Skeleton height={110} /></>}
          {jobsQ.data && jobs.length === 0 && <p className="panel body-3">{t("didi.empty")}</p>}
          {jobs.map((j) => <TicketCard key={j.id} job={j} onOpen={() => setOpenId(j.id)} />)}
        </section>
      )}
    </main>
  );
}

function ProfileBar({ p }: { p: DidiProfile }) {
  return (
    <header className="panel didi-profile">
      <div className="avatar" aria-hidden="true">{p.name.slice(0, 1)}</div>
      <div className="stack" style={{ gap: 2, flex: 1, minWidth: 200 }}>
        <h1 className="heading-5">{t("didi.hello", { name: p.name })}</h1>
        <p className="body-6 muted"><Users size={14} aria-hidden="true" /> {p.shg} · {p.village}</p>
        <p className="body-6 muted"><Plane size={14} aria-hidden="true" /> {p.drone}</p>
      </div>
      <dl className="stats">
        <div><dt>{t("didi.stat.batteries")}</dt><dd className="num">{p.batteries_ready}</dd></div>
        <div><dt>{t("didi.stat.tank")}</dt><dd className="num">{fmt(p.tank_l, 0)} L</dd></div>
        <div><dt>{t("didi.stat.open")}</dt><dd className="num">{p.jobs_open}</dd></div>
        <div><dt>{t("didi.stat.done")}</dt><dd className="num">{p.jobs_done}</dd></div>
        <div><dt>{t("didi.stat.saved")}</dt><dd className="num">{fmt(p.pesticide_saved, 0)} {p.pesticide_unit}</dd></div>
      </dl>
    </header>
  );
}

function TicketCard({ job, onOpen }: { job: Job; onOpen: () => void }) {
  const tk = job.ticket;
  const first = job.schedule[0];
  return (
    <button type="button" className={`panel ticket ${job.mode === "spray" && job.status === "new" ? "urgent" : ""}`} onClick={onOpen}>
      <div className="avatar small" aria-hidden="true">{tk.farmer.slice(0, 1)}</div>
      <div className="stack" style={{ gap: "var(--s-50)", flex: 1, minWidth: 0, textAlign: "left" }}>
        <p className="heading-6">{tk.farmer} <span className="body-6 muted">· {tk.village} · {t("didi.khasra", { k: tk.khasra })}</span></p>
        <div className="row" style={{ gap: "var(--s-75)" }}>
          <span className={`chip ${STATUS_CHIP[job.status]}`}>{t(`didi.status.${job.status}` as Key)}</span>
          <span className="chip level-low">{t(`didi.mode.${job.mode}` as Key)}</span>
          {first && <span className="chip level-low num">{first.date.slice(5)} · {first.time}</span>}
          <span className="body-6 num">{causeName(tk.cause)} · {Math.round(tk.confidence * 100)}% · {fmt(job.plan.zone_acres, 2)} {t("didi.acre")}</span>
        </div>
      </div>
      <div className="stack" style={{ gap: 0, alignItems: "flex-end" }}>
        <span className="big-num num">{fmt(tk.distance_km)}</span><span className="caption-5">{t("didi.km")}</span>
      </div>
      <ChevronRight aria-hidden="true" size={28} />
    </button>
  );
}

/** Position along the route polyline for progress 0..1, plus the part already sprayed. */
function along(path: [number, number][], p: number) {
  if (path.length < 2) return { at: path[0] ?? null, done: path };
  const seg = path.slice(1).map((q, i) => Math.hypot(q[0] - path[i][0], q[1] - path[i][1]));
  const total = seg.reduce((a, b) => a + b, 0);
  let left = p * total;
  for (let i = 0; i < seg.length; i++) {
    if (left <= seg[i]) {
      const k = seg[i] ? left / seg[i] : 0, a = path[i], b = path[i + 1];
      const at: [number, number] = [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];
      return { at, done: [...path.slice(0, i + 1), at], line: Math.floor(i / 2) + 1 };
    }
    left -= seg[i];
  }
  return { at: path[path.length - 1], done: path, line: Math.ceil(seg.length / 2) };
}

function TicketDetail({ job, onBack, onChange }: { job: Job; onBack: () => void; onChange: () => void }) {
  const tk = job.ticket;
  const spray = job.plan.spray;
  const s = job.savings;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(job.status === "done" ? 1 : 0);
  const [paused, setPaused] = useState(false);
  const raf = useRef(0);

  // Drone replay: the dot on the map moves along the same waypoints the drone flies.
  useEffect(() => {
    if (job.status !== "flying" || paused) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setProgress(1); return; }
    let last = performance.now();
    const tick = (now: number) => {
      let finished = false;
      setProgress((p) => {
        const next = Math.min(1, p + (now - last) / 1000 / FLIGHT_DEMO_S);
        finished = next >= 1;
        return next;
      });
      last = now;
      if (!finished) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [job.status, paused]);

  const pos = useMemo(() => along(job.route.waypoints, progress), [job.route.waypoints, progress]);
  const lines = job.route.passes;
  const minutesLeft = job.route.minutes * (1 - progress);
  const tankLeft = spray ? spray.water_l * (1 - progress) : 0;

  async function act(action: string) {
    setBusy(true); setError(null);
    try { await api.jobAction(job.id, action); if (action === "start") setProgress(0); onChange(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const needsVerify = job.mode === "verify_then_spray" && !job.window.verified;
  const done = job.status === "done";

  return (
    <div className="stack">
      <div className="row">
        <button type="button" className="btn btn-icon" aria-label={t("didi.back")} onClick={onBack}><ArrowLeft /></button>
        <div className="stack" style={{ gap: 0, flex: 1 }}>
          <h2 className="heading-5">{tk.farmer} · {tk.village}</h2>
          <p className="body-6 muted num">{t("didi.khasra", { k: tk.khasra })} · {t("didi.crop_days", { d: tk.crop_days })} · {fmt(tk.distance_km)} {t("didi.km")}</p>
        </div>
        <span className={`chip ${STATUS_CHIP[job.status]}`}>{t(`didi.status.${job.status}` as Key)}</span>
      </div>

      <div className="ticket-grid">
        {/* 1. Problem */}
        <section className="panel stack" aria-labelledby="sec-problem">
          <h3 id="sec-problem" className="heading-6"><Stethoscope size={22} aria-hidden="true" /> {t("didi.sec.problem")}</h3>
          <p className="title-2">{t("ev.suspected", { cause: causeName(tk.cause) })}
            <span className={`chip level-${tk.level ?? "low"}`} style={{ marginLeft: 8 }}>{Math.round(tk.confidence * 100)}%</span></p>
          <ul className="body-6 plain">{tk.symptoms.map((x) => <li key={x}>{x}</li>)}</ul>
          {job.mode === "verify_then_spray" && <p className="notice notice-warn body-6">{t("didi.verify_note")}</p>}
        </section>

        {/* 2. What + how much */}
        <section className="panel stack" aria-labelledby="sec-what">
          <h3 id="sec-what" className="heading-6"><Droplets size={22} aria-hidden="true" /> {t("didi.sec.what")}</h3>
          {spray ? (
            <>
              <p className="body-3">{spray.product}</p>
              <div className="mix">
                <div><span className="big-num num">{fmt(spray.quantity)}</span><span className="caption-5">{spray.unit} {t("didi.medicine")}</span></div>
                <span className="heading-5" aria-hidden="true">+</span>
                <div><span className="big-num num">{fmt(spray.water_l)}</span><span className="caption-5">L {t("didi.water")}</span></div>
              </div>
              <p className="body-6 muted num">{t("didi.dose_acre", { d: fmt(spray.dose_per_acre), u: spray.unit })} · {fmt(job.plan.zone_acres, 2)} {t("didi.acre")}</p>
            </>
          ) : <p className="body-3">{job.plan.cultural[0]}</p>}
          <p className="notice notice-warn body-6"><ShieldCheck size={16} aria-hidden="true" /> {t("didi.safety")}</p>
          <p className="caption-5">{job.plan.source}</p>
        </section>

        {/* 3. Where: map follows the drone */}
        <section className="panel stack where" aria-labelledby="sec-where">
          <h3 id="sec-where" className="heading-6"><MapPinned size={22} aria-hidden="true" /> {t("didi.sec.where")}</h3>
          <div className="didi-map">
            <FieldMap field={tk.field} zone={job.route.zone} route={job.route.path} sprayed={pos.done} drone={progress > 0 ? pos.at : null}
              label="Spray zone, route and drone position" />
          </div>
          <div className="mission-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
            <i style={{ transform: `scaleX(${progress})` }} />
          </div>
          <div className="row spread body-6 num">
            <span><Timer size={14} aria-hidden="true" /> {t("didi.line", { a: Math.min(pos.line ?? 0, lines), b: lines })}</span>
            <span>{t("didi.min_left", { m: fmt(minutesLeft) })}</span>
            {spray && <span><Droplets size={14} aria-hidden="true" /> {t("didi.tank_left", { l: fmt(tankLeft) })}</span>}
            <span>{Math.round(progress * 100)}%</span>
          </div>
        </section>

        {/* 4. When: schedule */}
        <section className="panel stack" aria-labelledby="sec-when">
          <h3 id="sec-when" className="heading-6"><CalendarClock size={22} aria-hidden="true" /> {t("didi.sec.when")}</h3>
          <ol className="schedule">
            {job.schedule.map((v, i) => (
              <li key={i} className={i === 0 ? "now" : ""}>
                <span className="num when">{v.date.slice(8)}/{v.date.slice(5, 7)}<br /><b>{v.time}</b></span>
                <span className="body-6">{v.note_hi}</span>
              </li>
            ))}
          </ol>
          <div className="slots" role="list" aria-label="Spray window">
            {job.window.slots.map((x) => (
              <span key={x.time} role="listitem" className={`num ${!x.ok ? "bad" : x.time === job.window.best ? "best" : ""}`}
                title={`${x.time.slice(11, 16)} · ${x.rain_mm} mm · ${x.wind_kmh ?? "?"} km/h`}>{x.time.slice(11, 13)}</span>
            ))}
          </div>
          <p className="caption-5"><CloudRain size={12} aria-hidden="true" /> <Wind size={12} aria-hidden="true" /> {t("didi.window_rule")}</p>
        </section>
      </div>

      {error && <ErrorNotice error={error} />}
      <div className="row" aria-live="polite">
        {job.status === "new" && <>
          <button type="button" className="btn btn-primary btn-big" style={{ flex: 2 }} disabled={busy} onClick={() => act("accept")}>{t("didi.accept")}</button>
          <button type="button" className="btn btn-big" style={{ flex: 1 }} disabled={busy} onClick={() => act("decline")}>{t("didi.decline")}</button>
        </>}
        {job.status === "accepted" && needsVerify && <>
          <button type="button" className="btn btn-primary btn-big" style={{ flex: 1 }} disabled={busy} onClick={() => act("verified")}>{t("didi.verified")}</button>
          <button type="button" className="btn btn-big" style={{ flex: 1 }} disabled={busy} onClick={() => act("rejected")}>{t("didi.rejected")}</button>
        </>}
        {job.status === "accepted" && !needsVerify && (
          <button type="button" className="btn btn-alert btn-big" disabled={busy} onClick={() => act("start")}><Plane aria-hidden="true" /> {t("didi.start")}</button>
        )}
        {job.status === "flying" && <>
          <button type="button" className="btn btn-big" style={{ flex: 1 }} onClick={() => setPaused((x) => !x)}>
            {paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />} {paused ? t("didi.resume") : t("didi.pause")}
          </button>
          <button type="button" className="btn btn-primary btn-big" style={{ flex: 2 }} disabled={busy || progress < 0.99} onClick={() => act("complete")}>{t("didi.complete")}</button>
        </>}
        <a className="btn" href={api.waypointsUrl(job.id)} download><Download aria-hidden="true" size={18} /> {t("didi.waypoints")}</a>
      </div>

      {/* 5. Savings, last */}
      <section className={`panel stack savings ${done ? "done" : ""}`} aria-labelledby="sec-saved">
        <h3 id="sec-saved" className="heading-6"><Leaf size={22} aria-hidden="true" /> {done ? t("didi.saved_title_done") : t("didi.saved_title")}</h3>
        <p className="body-6 muted num">{t("didi.saved_vs", { a: fmt(s.acres_not_sprayed, 2), m: fmt(s.full_field_minutes) })}</p>
        <div className="save-grid">
          <div><Droplets aria-hidden="true" /><span className="big-num num">{fmt(s.pesticide.saved)}</span><span className="caption-5">{s.pesticide.unit ?? ""} {t("didi.save.pesticide")}</span></div>
          <div><CloudRain aria-hidden="true" /><span className="big-num num">{fmt(s.water_l.saved)}</span><span className="caption-5">L {t("didi.save.water")}</span></div>
          <div><Fuel aria-hidden="true" /><span className="big-num num">{fmt(s.fuel_l.saved, 2)}</span><span className="caption-5">L {t("didi.save.fuel")}</span></div>
          <div><BatteryFull aria-hidden="true" /><span className="big-num num">{fmt(s.battery.saved)}</span><span className="caption-5">{t("didi.save.battery")}</span></div>
        </div>
        <p className="caption-5">{s.fuel_l.note}</p>
      </section>
    </div>
  );
}
