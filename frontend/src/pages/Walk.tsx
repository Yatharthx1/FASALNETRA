import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, Check, Footprints, Navigation, Volume2 } from "lucide-react";
import CameraGuide from "../components/CameraGuide";
import FieldMap from "../components/FieldMap";
import FarmerResult from "../components/FarmerResult";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api } from "../lib/api";
import { bearing, metres, polygonAcres, stepTowards, turn, type LonLat } from "../lib/geo";
import { fmt, speak, t, type Key } from "../lib/i18n";
import { askMotionPermission, useCamera, useGps, useHeading } from "../lib/sensors";
import type { Case, Field } from "../types/api";

type Step =
  | { kind: "welcome" }
  | { kind: "guide"; cell: number }
  | { kind: "photo"; cell: number; side: "top" | "under" }
  | { kind: "loop"; wp: number }
  | { kind: "sending" }
  | { kind: "result" };

const ARRIVE_M = 6;          // within one Sentinel-2 cell
const LOOP_ARRIVE_M = 4;
const DEMO_STEP_M = 3.5;     // demo walk: metres per tick (about 2.5x walking pace)
const DEMO_TICK_MS = 1000;
const TURN_RATE = 35;        // demo walker turns this many degrees per tick
const GPS_OK_M = 30;
const SPEAK_GAP_MS = 4500;

export default function Walk() {
  const token = new URLSearchParams(location.search).get("t") ?? "";
  const caseQ = useAsync(() => api.caseByToken(token), [token]);
  const fieldQ = useAsync(() => api.field(), []);
  const walkQ = useAsync(() => api.demoWalk(), []);

  if (caseQ.error) return <main className="walk"><p className="notice notice-error" role="alert">{t("walk.link_bad")}</p></main>;
  if (fieldQ.error) return <main className="walk"><ErrorNotice error={fieldQ.error} onRetry={fieldQ.reload} /></main>;
  if (!caseQ.data || !fieldQ.data || !walkQ.data) {
    return <main className="walk" aria-busy="true"><Skeleton height={60} /><Skeleton height={420} /><Skeleton height={84} /></main>;
  }
  return <WalkFlow initial={caseQ.data} field={fieldQ.data} loopPath={walkQ.data} />;
}

function WalkFlow({ initial, field, loopPath }: { initial: Case; field: Field; loopPath: LonLat[] }) {
  const [kase, setKase] = useState(initial);
  const [step, setStep] = useState<Step>({ kind: "welcome" });
  const [status, setStatus] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [trail, setTrail] = useState<LonLat[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const live = step.kind !== "welcome" && step.kind !== "result";
  const cam = useCamera(live && step.kind !== "sending");
  const { fix, denied } = useGps(live);
  const compass = useHeading(live);

  // Demo walker: used when there is no usable GPS (laptop demo, indoors) or ?demo=1.
  const forcedDemo = new URLSearchParams(location.search).get("demo") === "1";
  const [noGps, setNoGps] = useState(false);
  useEffect(() => {
    if (!live) return;
    const id = setTimeout(() => setNoGps(!fix || fix.accuracy > GPS_OK_M), 4000);
    return () => clearTimeout(id);
  }, [live, fix]);
  const demo = forcedDemo || denied || noGps;
  const start = field.geometry.coordinates[0][0] as LonLat;
  const [demoPos, setDemoPos] = useState<LonLat>(start);
  const [demoHeading, setDemoHeading] = useState(0);

  const targets = kase.target_cells;
  const target: LonLat | null =
    step.kind === "guide" ? targets[step.cell].centre
      : step.kind === "loop" ? loopPath[step.wp % loopPath.length]
        : null;

  useEffect(() => {
    if (!demo || !target) return;
    const id = setInterval(() => {
      setDemoHeading((h) => {
        const want = bearing(demoPos, target);
        const d = turn(h, want);
        return (h + Math.max(-TURN_RATE, Math.min(TURN_RATE, d)) + 360) % 360;
      });
      setDemoPos((p) => (Math.abs(turn(demoHeading, bearing(p, target))) < 50 ? stepTowards(p, target, DEMO_STEP_M) : p));
    }, DEMO_TICK_MS);
    return () => clearInterval(id);
  }, [demo, target, demoPos, demoHeading]);

  const pos: LonLat | null = demo ? demoPos : fix?.pos ?? null;
  const heading = demo ? demoHeading : compass ?? fix?.course ?? null;
  const dist = pos && target ? metres(pos, target) : null;
  const turnDeg = pos && target && heading !== null ? turn(heading, bearing(pos, target)) : null;
  const arrived = dist !== null && dist <= (step.kind === "loop" ? LOOP_ARRIVE_M : ARRIVE_M);

  // Voice guidance: say the instruction when it changes, not every second.
  const said = useRef({ key: "", at: 0 });
  const instruction: Key | null =
    step.kind === "guide" ? (arrived ? "guide.arrived" : turnDeg === null ? "guide.follow_map"
      : Math.abs(turnDeg) > 110 ? "guide.back" : turnDeg > 25 ? "guide.right" : turnDeg < -25 ? "guide.left" : "guide.straight")
      : step.kind === "loop" ? (turnDeg !== null && Math.abs(turnDeg) > 25 ? (turnDeg > 0 ? "guide.right" : "guide.left") : "guide.loop")
        : null;
  useEffect(() => {
    if (!instruction) return;
    const now = Date.now();
    if (instruction !== said.current.key && now - said.current.at > (instruction === "guide.arrived" ? 0 : SPEAK_GAP_MS)) {
      said.current = { key: instruction, at: now };
      speak(t(instruction));
    }
  }, [instruction]);

  useEffect(() => { if (arrived && step.kind === "guide") navigator.vibrate?.([200, 80, 200]); }, [arrived, step.kind]);

  // Patch loop: record the walked trail and move to the next corner when the farmer reaches it.
  useEffect(() => {
    if (step.kind !== "loop" || !pos) return;
    setTrail((tr) => (tr.length && metres(tr[tr.length - 1], pos) < 2 ? tr : [...tr, pos]));
    if (arrived) {
      if (step.wp + 1 >= loopPath.length + 1) void finishLoop();
      else setStep({ kind: "loop", wp: step.wp + 1 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, pos?.[0], pos?.[1], arrived]);

  async function begin() {
    await askMotionPermission();
    setStep({ kind: "guide", cell: 0 });
  }

  async function takePhoto(file?: Blob | null) {
    if (step.kind !== "photo") return;
    const blob = file ?? (await cam.capture());
    if (!blob) { fileRef.current?.click(); return; }
    setBusy(true);
    setStatus({ tone: "warn", text: t("walk.photo.checking") });
    try {
      const at = pos ?? targets[step.cell].centre;
      const photo = await api.uploadPhoto(kase.id, blob, {
        kind: step.side === "top" ? "leaf_top" : "leaf_under", spot: step.cell, cell_id: targets[step.cell].id, lon: at[0], lat: at[1],
      });
      const retake = photo.vision.quality.retake_reason;
      if (retake) {
        const msg = t(retake === "dark" ? "walk.photo.dark" : "walk.photo.blurry");
        setStatus({ tone: "error", text: msg });
        speak(msg);
        return;
      }
      setStatus({ tone: "ok", text: t("walk.photo.ok") });
      setKase(await api.getCase(kase.id));
      if (step.side === "top") setStep({ kind: "photo", cell: step.cell, side: "under" });
      else if (step.cell + 1 < targets.length) setStep({ kind: "guide", cell: step.cell + 1 });
      else { setTrail([]); setStep({ kind: "loop", wp: 0 }); }
      speak(t(step.side === "top" ? "walk.photo.under.say" : "walk.photo.ok"));
    } catch (e) {
      setStatus({ tone: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function finishLoop() {
    setStep({ kind: "sending" });
    try {
      const points = demo || trail.length < 3 ? loopPath : trail;
      await api.walk(kase.id, points);
      setKase(await api.evidence(kase.id));
      setStep({ kind: "result" });
    } catch (e) {
      setStatus({ tone: "error", text: (e as Error).message });
      setStep({ kind: "loop", wp: 0 });
    }
  }

  const sayText = useMemo(() => {
    switch (step.kind) {
      case "welcome": return t("walk.welcome.say2", { name: field.farmer.name });
      case "photo": return t(step.side === "top" ? "walk.photo.top.say" : "walk.photo.under.say");
      default: return "";
    }
  }, [step, field.farmer.name]);
  useEffect(() => { if (sayText && step.kind !== "welcome") speak(sayText); }, [sayText, step.kind]);

  const inset = pos && (
    <FieldMap field={field.geometry} targets={targets} activeTarget={step.kind === "guide" ? targets[step.cell].id : undefined}
      trail={step.kind === "loop" ? trail : []} me={pos} label="Small field map" compact />
  );

  if (step.kind === "result") return <FarmerResult kase={kase} field={field} onCase={setKase} />;

  if (step.kind === "welcome") {
    return (
      <main className="walk">
        <h1 className="heading-4">{t("walk.welcome.title", { name: field.farmer.name })}</h1>
        <p className="title-2 muted">{t("walk.welcome.field", { khasra: field.khasra, village: field.farmer.village })}</p>
        <button type="button" className="play" onClick={() => speak(sayText)}><Volume2 aria-hidden="true" size={28} /> {t("common.play")}</button>
        <div className="walk-map"><FieldMap field={field.geometry} targets={targets} label="Field map" /></div>
        <p className="body-3">{t("walk.welcome.how")}</p>
        <div className="walk-actions">
          <button type="button" className="btn btn-primary btn-big" onClick={begin}>
            <Camera aria-hidden="true" /> {t("walk.open_camera")}
          </button>
        </div>
      </main>
    );
  }

  const stepTitle =
    step.kind === "guide" ? t("walk.goto.cell", { i: step.cell + 1, n: targets.length })
      : step.kind === "photo" ? t(step.side === "top" ? "walk.photo.top.title" : "walk.photo.under.title")
        : step.kind === "loop" ? t("walk.patch.title") : t("walk.sending");

  return (
    <main className="walk walk-cam">
      <CameraGuide
        videoRef={cam.videoRef}
        cameraOn={cam.state === "on"}
        turnDeg={step.kind === "photo" || step.kind === "sending" ? null : turnDeg}
        arrived={step.kind === "photo" || (step.kind === "guide" && arrived)}
        inset={inset}
        top={
          <div className="cam-head">
            <p className="cam-title">{stepTitle}</p>
            {(step.kind === "guide" || step.kind === "loop") && dist !== null && (
              <p className={`cam-dist num ${arrived ? "ok" : ""}`} aria-live="polite">
                {arrived ? <><Check size={28} aria-hidden="true" /> {t("walk.goto.arrived")}</> : t("walk.goto.distance", { m: Math.round(dist) })}
              </p>
            )}
            {instruction && <p className="cam-say" aria-live="polite">{t(instruction)}</p>}
            {demo && <p className="cam-chip">{t("walk.demo_mode")}</p>}
            {cam.state === "denied" && <p className="cam-chip warn">{t("walk.camera_denied")}</p>}
          </div>
        }
      >
        {step.kind === "guide" && (
          <button type="button" className={`btn btn-big ${arrived ? "btn-primary" : "btn-glass"}`}
            onClick={() => setStep({ kind: "photo", cell: step.cell, side: "top" })}>
            <Navigation aria-hidden="true" /> {arrived ? t("common.next") : t("walk.goto.here")}
          </button>
        )}
        {step.kind === "photo" && (
          <>
            <p className="status-live" aria-live="polite">
              {status && <span className={`notice notice-${status.tone}`} style={{ display: "block" }}>{status.text}</span>}
            </p>
            <input ref={fileRef} id="photo-input" className="sr-only" type="file" accept="image/*" capture="environment"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void takePhoto(f); }} />
            <button type="button" className="shutter" disabled={busy} onClick={() => void takePhoto()} aria-label={t("walk.photo.take")}>
              <span />
            </button>
          </>
        )}
        {step.kind === "loop" && (
          <>
            <p className="cam-area num">{t("walk.patch.area", { acres: fmt(polygonAcres(trail), 2) })}</p>
            <button type="button" className="btn btn-big btn-glass" onClick={() => void finishLoop()}>
              <Footprints aria-hidden="true" /> {t("walk.patch.stop")}
            </button>
          </>
        )}
        {step.kind === "sending" && <p className="cam-say">{t("walk.sending")}</p>}
      </CameraGuide>
    </main>
  );
}
