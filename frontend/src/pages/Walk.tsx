import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, Check, Footprints, Navigation, Volume2 } from "lucide-react";
import CameraGuide from "../components/CameraGuide";
import FieldMap from "../components/FieldMap";
import FarmerResult from "../components/FarmerResult";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api } from "../lib/api";
import { bearing, metres, polygonAcres, stepTowards, turn, type LonLat } from "../lib/geo";
import { causeName, fmt, speak, t, type Key } from "../lib/i18n";
import { askMotionPermission, useCamera, useHeading } from "../lib/sensors";
import { createTrackUploader, useFusedPosition, type Sample } from "../lib/positioning";
import { useLeafScan, videoBox } from "../lib/leafScan";
import type { Case, Field, Located } from "../types/api";

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
const LOCATE_EVERY_MS = 60_000;
// Auto-capture on the phone, before any upload: the leaf is found by colour, held steady and sharp, then only the
// leaf is sent. Thresholds sit a little above the server gate (vision.quality); the server still has the final say.
const SHARP_MIN = 350;       // Laplacian variance on the 256 px leaf crop; ~server blur score 60 (step-blur check)
const BRIGHT_MIN = 45;       // 0-255
const STILL_MAX = 6;         // mean change between checks: the hand is steady
const LEAF_MIN = 0.08;       // leaf must fill this share of the frame: close enough to see spots
const STEADY_CHECKS = 3;     // ~0.7 s of good frames in a row
const GIVE_UP_CHECKS = 14;   // leaf in view and steady ~3 s but never "sharp": take it anyway, the server decides

export default function Walk() {
  const token = new URLSearchParams(location.search).get("t") ?? "";
  const caseQ = useAsync(() => api.caseByToken(token), [token]);
  // the case says which field: the demo parcel, or one resolved from the farmer's IVR onboarding
  const fieldId = caseQ.data?.field_id;
  const fieldQ = useAsync(() => (fieldId ? api.field(fieldId) : new Promise<never>(() => undefined)), [fieldId]);
  const walkQ = useAsync(() => (fieldId ? api.demoWalk(fieldId) : new Promise<never>(() => undefined)), [fieldId]);
  // tells the live call "link khul gaya" so the voice on the phone moves on with the farmer
  const caseId = caseQ.data?.id;
  useEffect(() => { if (caseId) api.opened(caseId).catch(() => undefined); }, [caseId]);

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
  const [advice, setAdvice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const live = step.kind !== "welcome" && step.kind !== "result";
  const cam = useCamera(live && step.kind !== "sending");
  const compass = useHeading(live);
  // 5 positions a second (GPS fixes + footsteps along the compass between them), uploaded in 2 s batches
  const uploader = useRef<ReturnType<typeof createTrackUploader> | null>(null);
  useEffect(() => {
    if (!live) return;
    const u = createTrackUploader((batch: Sample[]) => api.track(kase.id, batch.map((s) => ({
      t: s.t, lon: s.pos[0], lat: s.pos[1], accuracy: Math.min(s.accuracy, 5000), heading: s.heading,
      speed: Math.min(s.speed, 50), source: s.source }))));
    uploader.current = u;
    return () => { u.stop(); uploader.current = null; };
  }, [live, kase.id]);
  const { sample, denied } = useFusedPosition(live, compass, (s) => uploader.current?.push(s));
  const fix = sample ? { pos: sample.pos, accuracy: sample.accuracy, course: sample.heading } : null;
  const fixRef = useRef(fix);
  fixRef.current = fix;

  // Which parcel is the phone in? Checked once GPS is good, then every minute (status changes are logged).
  const [where, setWhere] = useState<Located | null>(null);
  const locatedAt = useRef(0);
  useEffect(() => {
    if (!sample || sample.accuracy > GPS_OK_M || Date.now() - locatedAt.current < LOCATE_EVERY_MS) return;
    locatedAt.current = Date.now();
    api.locate(kase.id, { lon: sample.pos[0], lat: sample.pos[1], accuracy: sample.accuracy }).then((w) => {
      setWhere((prev) => {
        if (w.status === "away" && prev?.status !== "away") speak(t("walk.where.away", { km: fmt(w.distance_m / 1000, 1) }));
        return w;
      });
    }).catch(() => undefined);
  }, [sample, kase.id]);
  const leaf = useLeafScan(cam.videoRef, step.kind === "photo" && cam.state === "on" && !busy);
  const leafClose = !!leaf?.box && leaf.leafFrac >= LEAF_MIN;
  const frameHint: Key | null = !leaf ? null
    : leaf.bright < BRIGHT_MIN ? "walk.photo.hint.dark"
      : !leaf.box ? "walk.photo.hint.no_leaf"
        : !leafClose ? "walk.photo.hint.closer"
          : leaf.sharp < SHARP_MIN || leaf.motion > STILL_MAX ? "walk.photo.hint.blurry" : "walk.photo.hint.ready";

  // Demo walker: used when there is no usable GPS (laptop demo, indoors) or ?demo=1.
  const forcedDemo = new URLSearchParams(location.search).get("demo") === "1";
  const [noGps, setNoGps] = useState(false);
  useEffect(() => {
    // samples arrive 5 times a second, so poll the latest one instead of waiting for a quiet spell
    if (!live) return;
    const id = setInterval(() => { const f = fixRef.current; setNoGps(!f || f.accuracy > GPS_OK_M); }, 4000);
    return () => clearInterval(id);
  }, [live]);
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

  // Auto-capture: the leaf close, bright, steady and sharp for ~0.7 s takes the photo (or ~3 s steady at all);
  // the shutter still works by hand.
  const steady = useRef({ ready: 0, held: 0 });
  useEffect(() => {
    const s = steady.current;
    s.ready = frameHint === "walk.photo.hint.ready" ? s.ready + 1 : 0;
    s.held = leafClose && leaf!.motion <= STILL_MAX && leaf!.bright >= BRIGHT_MIN ? s.held + 1 : 0;
    if ((s.ready >= STEADY_CHECKS || s.held >= GIVE_UP_CHECKS) && step.kind === "photo" && !busy) {
      steady.current = { ready: 0, held: 0 };
      void takePhoto();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaf]);

  async function begin() {
    await askMotionPermission();
    setStep({ kind: "guide", cell: 0 });
  }

  // set synchronously: auto-capture can fire again before the busy state re-renders (seen on a real phone)
  const uploading = useRef(false);

  async function takePhoto(file?: Blob | null) {
    if (step.kind !== "photo" || uploading.current) return;
    uploading.current = true;
    const v = cam.videoRef.current;
    const blob = file ?? (await cam.capture(leaf && v ? videoBox(leaf, v) : null));
    if (!blob) { uploading.current = false; fileRef.current?.click(); return; }
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
      const a = photo.vision.advice;
      if (a) {
        setAdvice([t("walk.photo.suspect", { name: causeName(a.cause) }),
          a.product ? t("walk.photo.use", { product: a.product }) : t("walk.photo.no_spray")].join(" · "));
      }
      setKase(await api.getCase(kase.id));
      if (step.side === "top") setStep({ kind: "photo", cell: step.cell, side: "under" });
      else if (step.cell + 1 < targets.length) setStep({ kind: "guide", cell: step.cell + 1 });
      else { setTrail([]); setStep({ kind: "loop", wp: 0 }); }
      speak(t(step.side === "top" ? "walk.photo.under.say" : "walk.photo.ok"));
    } catch (e) {
      setStatus({ tone: "error", text: (e as Error).message });
    } finally {
      uploading.current = false;
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
        leaf={step.kind === "photo" ? leaf : null}
        top={
          <div className="cam-head">
            <p className="cam-title">{stepTitle}</p>
            {(step.kind === "guide" || step.kind === "loop") && dist !== null && (
              <p className={`cam-dist num ${arrived ? "ok" : ""}`} aria-live="polite">
                {arrived ? <><Check size={28} aria-hidden="true" /> {t("walk.goto.arrived")}</> : t("walk.goto.distance", { m: Math.round(dist) })}
              </p>
            )}
            {instruction && <p className="cam-say" aria-live="polite">{t(instruction)}</p>}
            {step.kind === "guide" && targets[step.cell].reason && (
              <p className="cam-chip">{t(`walk.reason.${targets[step.cell].reason}` as Key)}</p>
            )}
            {step.kind === "photo" && cam.state === "on" && (
              <p className={`cam-chip ${frameHint === "walk.photo.hint.ready" ? "" : "warn"}`} aria-live="polite">
                {frameHint ? t(frameHint) : t("walk.photo.auto")}
              </p>
            )}
            {step.kind === "photo" && leaf?.box && (
              <p className="cam-chip num">{t("walk.photo.leaf_read", { y: leaf.yellowPct, b: leaf.brownPct })}</p>
            )}
            {advice && step.kind !== "photo" && <p className="cam-chip">{advice}</p>}
            {demo && <p className="cam-chip">{t("walk.demo_mode")}</p>}
            {!demo && sample && (
              <p className="cam-chip num">{t("walk.gps.live", { m: Math.round(sample.accuracy) })}</p>
            )}
            {where && !demo && (
              <p className={`cam-chip ${where.status === "on_field" ? "" : "warn"}`}>
                {where.status === "on_field"
                  ? t("walk.where.on_field", { khasra: where.parcel?.khasra ?? field.khasra })
                  : where.status === "near_field"
                    ? t("walk.where.near_field", { m: Math.round(where.distance_m) })
                    : t("walk.where.away", { km: fmt(where.distance_m / 1000, 1) })}
              </p>
            )}
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
            <button type="button" className={`shutter ${frameHint === "walk.photo.hint.ready" ? "shutter-ready" : ""}`} disabled={busy}
              onClick={() => void takePhoto()} aria-label={t("walk.photo.take")}>
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
