import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft, Bell, CheckCircle2, ChevronRight, Droplets, MapPin, Phone,
  ShieldCheck, Stethoscope, Users
} from "lucide-react";
import AnimatedFieldGraphic from "../components/AnimatedFieldGraphic";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api, eventsSocket } from "../lib/api";
import { causeName, fmt, speak, t, type Key } from "../lib/i18n";
import type { DidiProfile, Job } from "../types/api";

const STATUS_CHIP: Record<Job["status"], string> = {
  new: "band-high",
  accepted: "band-watch",
  flying: "band-watch",
  done: "band-safe",
  declined: "level-low"
};

export default function Didi() {
  const profileQ = useAsync(() => api.didiProfile(), []);
  const jobsQ = useAsync(() => api.jobs(), []);
  const [openId, setOpenId] = useState<number | null>(null);
  const [tab, setTab] = useState<"pending" | "closed">("pending");
  const reload = useCallback(() => { jobsQ.reload(); profileQ.reload(); }, [jobsQ.reload, profileQ.reload]);

  // Real-time alert when a new farmer request arrives
  const seen = useRef<Set<number> | null>(null);
  const [alert, setAlert] = useState<Job | null>(null);
  const [canNotify, setCanNotify] = useState(() => typeof Notification !== "undefined" && Notification.permission === "granted");

  useEffect(() => eventsSocket((e) => {
    if (e.type === "demo_reset") { seen.current = null; setAlert(null); }
    if (e.type.startsWith("didi_") || e.type === "zone_mapped" || e.type === "demo_reset") reload();
  }), [reload]);

  const jobs = jobsQ.data ?? [];
  const pendingJobs = jobs.filter((j) => j.status !== "done" && j.status !== "declined");
  const closedJobs = jobs.filter((j) => j.status === "done" || j.status === "declined");

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

  const open = jobs.find((j) => j.id === openId) ?? null;

  return (
    <main className="didi">
      {profileQ.data ? (
        <ProfileHeader p={profileQ.data} pendingCount={pendingJobs.length} closedCount={closedJobs.length} />
      ) : (
        <Skeleton height={88} />
      )}

      {(jobsQ.error || profileQ.error) && (
        <ErrorNotice error={(jobsQ.error || profileQ.error)!} onRetry={reload} />
      )}

      {!canNotify && typeof Notification !== "undefined" && Notification.permission === "default" && (
        <button type="button" className="btn" onClick={() => Notification.requestPermission().then((p) => setCanNotify(p === "granted"))}>
          <Bell size={18} aria-hidden="true" /> {t("didi.notify_on")}
        </button>
      )}

      {alert && (
        <section className="notice notice-ok row spread" role="alert">
          <p className="heading-6">
            <Bell size={20} aria-hidden="true" /> {t("didi.new_request", { farmer: alert.ticket.farmer, village: alert.ticket.village, khasra: alert.ticket.khasra })}
          </p>
          <button type="button" className="btn btn-primary" onClick={() => { setOpenId(alert.id); setAlert(null); }}>
            {t("didi.open_request")}
          </button>
        </section>
      )}

      {open ? (
        <TicketDetail key={open.id} job={open} onBack={() => setOpenId(null)} onChange={reload} />
      ) : (
        <section className="stack">
          {/* Segmented Tab Navigation for Pending vs Closed Tickets */}
          <nav className="didi-tabs" aria-label="Ticket status tabs">
            <button
              type="button"
              className={`didi-tab-btn ${tab === "pending" ? "active" : ""}`}
              onClick={() => setTab("pending")}
            >
              <span>⏳ {t("didi.tabs.pending")}</span>
              <span className="badge">{pendingJobs.length}</span>
            </button>
            <button
              type="button"
              className={`didi-tab-btn ${tab === "closed" ? "active" : ""}`}
              onClick={() => setTab("closed")}
            >
              <span>✅ {t("didi.tabs.closed")}</span>
              <span className="badge">{closedJobs.length}</span>
            </button>
          </nav>

          {jobsQ.loading && !jobsQ.data && (
            <>
              <Skeleton height={100} />
              <Skeleton height={100} />
            </>
          )}

          {tab === "pending" && (
            <div className="stack">
              {pendingJobs.length === 0 && (
                <p className="panel body-3 text-center">{t("didi.no_pending")}</p>
              )}
              {pendingJobs.map((j) => (
                <TicketCard key={j.id} job={j} onOpen={() => setOpenId(j.id)} />
              ))}
            </div>
          )}

          {tab === "closed" && (
            <div className="stack">
              {closedJobs.length === 0 && (
                <p className="panel body-3 text-center">{t("didi.no_closed")}</p>
              )}
              {closedJobs.map((j) => (
                <TicketCard key={j.id} job={j} onOpen={() => setOpenId(j.id)} />
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function ProfileHeader({ p, pendingCount, closedCount }: { p: DidiProfile; pendingCount: number; closedCount: number }) {
  return (
    <header className="panel didi-profile">
      <div className="avatar" aria-hidden="true">{p.name.slice(0, 1)}</div>
      <div className="stack" style={{ gap: 2, flex: 1, minWidth: 200 }}>
        <h1 className="heading-5">{t("didi.hello", { name: p.name })}</h1>
        <p className="body-6 muted">
          <Users size={14} aria-hidden="true" /> {p.shg} · {p.village}
        </p>
      </div>
      <div className="row" style={{ gap: "var(--s-100)" }}>
        <span className="chip band-watch num">⏳ {pendingCount} {t("didi.tabs.pending")}</span>
        <span className="chip band-safe num">✅ {closedCount} {t("didi.tabs.closed")}</span>
      </div>
    </header>
  );
}

function TicketCard({ job, onOpen }: { job: Job; onOpen: () => void }) {
  const tk = job.ticket;
  const isDone = job.status === "done";
  const patchAcres = tk.zone_acres ?? job.plan.zone_acres;

  return (
    <button
      type="button"
      className={`panel ticket ${job.status === "new" ? "urgent" : ""}`}
      onClick={onOpen}
    >
      <div className="avatar small" aria-hidden="true">{tk.farmer.slice(0, 1)}</div>
      <div className="stack" style={{ gap: "var(--s-50)", flex: 1, minWidth: 0, textAlign: "left" }}>
        <p className="heading-6">
          {tk.farmer} <span className="body-6 muted">· {tk.village} · {t("didi.khasra", { k: tk.khasra })}</span>
        </p>
        <div className="row" style={{ gap: "var(--s-75)", flexWrap: "wrap" }}>
          <span className={`chip ${STATUS_CHIP[job.status]}`}>{t(`didi.status.${job.status}` as Key)}</span>
          <span className="body-6 num">
            {causeName(tk.cause)} · {Math.round(tk.confidence * 100)}%
          </span>
          <span className="body-6 muted num">
            · {t("didi.patch_of_field", { zone: fmt(patchAcres, 2), field: fmt(tk.field_acres, 2) })}
          </span>
        </div>
      </div>
      <div className="stack" style={{ gap: 0, alignItems: "flex-end" }}>
        <span className="big-num num">{fmt(tk.distance_km)}</span>
        <span className="caption-5">{t("didi.km")}</span>
      </div>
      <ChevronRight aria-hidden="true" size={28} />
    </button>
  );
}

function TicketDetail({ job, onBack, onChange }: { job: Job; onBack: () => void; onChange: () => void }) {
  const tk = job.ticket;
  const spray = job.plan.spray;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patchAcres = tk.zone_acres ?? job.plan.zone_acres;
  const zoneGeom = tk.zone ?? job.route.zone;
  const walkTrail = tk.walk_trail ?? [];

  async function act(action: string) {
    setBusy(true);
    setError(null);
    try {
      await api.jobAction(job.id, action);
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const isDone = job.status === "done";

  return (
    <div className="stack">
      {/* Detail Header */}
      <div className="row spread" style={{ alignItems: "center" }}>
        <div className="row" style={{ gap: "var(--s-100)", alignItems: "center" }}>
          <button type="button" className="btn btn-icon" aria-label={t("didi.back")} onClick={onBack}>
            <ArrowLeft />
          </button>
          <div className="stack" style={{ gap: 2 }}>
            <h2 className="heading-5">{tk.farmer} · {tk.village}</h2>
            <p className="body-6 muted num">
              {t("didi.khasra", { k: tk.khasra })} · {t("didi.crop_days", { d: tk.crop_days })} · {fmt(tk.distance_km)} {t("didi.km")}
            </p>
          </div>
        </div>
        <div className="row" style={{ gap: "var(--s-100)", alignItems: "center" }}>
          {tk.phone && (
            <a href={`tel:${tk.phone}`} className="btn">
              <Phone size={16} aria-hidden="true" /> {t("didi.call")}
            </a>
          )}
          <span className={`chip ${STATUS_CHIP[job.status]}`}>{t(`didi.status.${job.status}` as Key)}</span>
        </div>
      </div>

      {error && <ErrorNotice error={error} />}

      {/* Hero: Satellite Map Graphic showing the location fetched from the farmer via the webpage */}
      <section className="panel stack" aria-labelledby="map-graphic-title">
        <div className="row spread">
          <h3 id="map-graphic-title" className="heading-6">
            <MapPin size={22} aria-hidden="true" /> {t("didi.sec.where")}
          </h3>
          <span className="caption-5 muted">
            {t("didi.patch_of_field", { zone: fmt(patchAcres, 2), field: fmt(tk.field_acres, 2) })}
          </span>
        </div>

        <div className="didi-map-graphic">
          <AnimatedFieldGraphic
            field={tk.field}
            zone={zoneGeom}
            trail={walkTrail}
            khasra={tk.khasra}
            fieldAcres={tk.field_acres}
            patchAcres={patchAcres}
          />
        </div>

        {/* Legend explaining the map graphics derived from the farmer's web walk */}
        <div className="map-legend-bar" role="note">
          <div className="map-legend-item">
            <span className="legend-dot field" aria-hidden="true" />
            <span>{t("didi.legend_field")} ({fmt(tk.field_acres, 2)} {t("didi.acre")})</span>
          </div>
          <div className="map-legend-item">
            <span className="legend-dot patch" aria-hidden="true" />
            <span><strong>{t("didi.legend_patch")} ({fmt(patchAcres, 2)} {t("didi.acre")})</strong></span>
          </div>
          {walkTrail.length > 0 && (
            <div className="map-legend-item">
              <span className="legend-dot trail" aria-hidden="true" />
              <span>{t("didi.legend_trail")} ({walkTrail.length} GPS fixes)</span>
            </div>
          )}
        </div>
      </section>

      {/* Ticket Details & Advisory */}
      <div className="ticket-grid">
        {/* Problem Diagnosis */}
        <section className="panel stack" aria-labelledby="sec-problem">
          <h3 id="sec-problem" className="heading-6">
            <Stethoscope size={22} aria-hidden="true" /> {t("didi.sec.problem")}
          </h3>
          <p className="title-2">
            {t("ev.suspected", { cause: causeName(tk.cause) })}
            <span className={`chip level-${tk.level ?? "low"}`} style={{ marginLeft: 8 }}>
              {Math.round(tk.confidence * 100)}%
            </span>
          </p>
          <p className="body-6 muted">
            {t("didi.khasra", { k: tk.khasra })} · {t("didi.crop_days", { d: tk.crop_days })}
          </p>
          <p className="body-6">
            {t("didi.patch_of_field", { zone: fmt(patchAcres, 2), field: fmt(tk.field_acres, 2) })}
          </p>
        </section>

        {/* Treatment Recommendation */}
        <section className="panel stack" aria-labelledby="sec-what">
          <h3 id="sec-what" className="heading-6">
            <Droplets size={22} aria-hidden="true" /> {t("didi.sec.what")}
          </h3>
          {spray ? (
            <>
              <p className="body-3"><strong>{spray.product}</strong></p>
              <div className="mix">
                <div>
                  <span className="big-num num">{fmt(spray.quantity)}</span>
                  <span className="caption-5">{spray.unit} {t("didi.medicine")}</span>
                </div>
                <span className="heading-5" aria-hidden="true">+</span>
                <div>
                  <span className="big-num num">{fmt(spray.water_l)}</span>
                  <span className="caption-5">L {t("didi.water")}</span>
                </div>
              </div>
              <p className="body-6 muted num">
                {t("didi.dose_acre", { d: fmt(spray.dose_per_acre), u: spray.unit })} · {fmt(patchAcres, 2)} {t("didi.acre")}
              </p>
            </>
          ) : (
            <p className="body-3">{job.plan.cultural?.[0] ?? "No chemical spray needed"}</p>
          )}
          <p className="notice notice-warn body-6">
            <ShieldCheck size={16} aria-hidden="true" /> {t("didi.safety")}
          </p>
        </section>
      </div>

      {/* Clean Status Actions */}
      <div className="row" aria-live="polite" style={{ marginTop: "var(--s-100)" }}>
        {job.status === "new" && (
          <>
            <button
              type="button"
              className="btn btn-primary btn-big"
              style={{ flex: 2 }}
              disabled={busy}
              onClick={() => act("accept")}
            >
              {t("didi.accept")}
            </button>
            <button
              type="button"
              className="btn btn-big"
              style={{ flex: 1 }}
              disabled={busy}
              onClick={() => act("decline")}
            >
              {t("didi.decline")}
            </button>
          </>
        )}

        {(job.status === "accepted" || job.status === "flying") && (
          <button
            type="button"
            className="btn btn-primary btn-big"
            style={{ width: "100%" }}
            disabled={busy}
            onClick={() => act("complete")}
          >
            <CheckCircle2 size={20} aria-hidden="true" /> {t("didi.mark_done")}
          </button>
        )}

        {isDone && (
          <div className="panel row" style={{ width: "100%", justifyContent: "center", background: "var(--leaf-100)" }}>
            <span className="heading-6" style={{ color: "var(--leaf-800)", display: "flex", alignItems: "center", gap: 8 }}>
              <CheckCircle2 size={22} /> {t("didi.status.done")}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
