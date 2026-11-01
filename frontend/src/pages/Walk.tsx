import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Phone, Volume2 } from "lucide-react";
import CameraGuide from "../components/CameraGuide";
import { ErrorNotice, Skeleton, useAsync } from "../components/common";
import { api } from "../lib/api";
import { causeName, speak, t, type Key } from "../lib/i18n";
import { useCamera } from "../lib/sensors";
import { useLeafScan, videoBox } from "../lib/leafScan";
import type { Case, Field } from "../types/api";

// The WhatsApp link opens straight on the camera: one sharp leaf photo, then the result is spoken on the call.
type Step = "photo" | "sending" | "done";

const POLL_MS = 1500;
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
  const fieldId = caseQ.data?.field_id;
  const fieldQ = useAsync(() => (fieldId ? api.field(fieldId) : new Promise<never>(() => undefined)), [fieldId]);
  // the patch Drone Didi sprays: the satellite-flagged loop on the farmer's parcel (no walking in the demo flow)
  const patchQ = useAsync(() => (fieldId ? api.demoWalk(fieldId) : new Promise<never>(() => undefined)), [fieldId]);
  // tells the live call "link khul gaya" so the voice on the phone moves on with the farmer
  const caseId = caseQ.data?.id;
  useEffect(() => { if (caseId) api.opened(caseId).catch(() => undefined); }, [caseId]);

  if (caseQ.error) return <main className="walk"><p className="notice notice-error" role="alert">{t("walk.link_bad")}</p></main>;
  if (fieldQ.error) return <main className="walk"><ErrorNotice error={fieldQ.error} onRetry={fieldQ.reload} /></main>;
  if (!caseQ.data || !fieldQ.data || !patchQ.data) {
    return <main className="walk" aria-busy="true"><Skeleton height={60} /><Skeleton height={420} /><Skeleton height={84} /></main>;
  }
  return <LeafFlow initial={caseQ.data} field={fieldQ.data} patch={patchQ.data} />;
}

function LeafFlow({ initial, field, patch }: { initial: Case; field: Field; patch: [number, number][] }) {
  const [kase, setKase] = useState(initial);
  const [step, setStep] = useState<Step>(initial.evidence ? "done" : "photo");
  const [status, setStatus] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const cam = useCamera(step === "photo");
  const leaf = useLeafScan(cam.videoRef, step === "photo" && cam.state === "on" && !busy);
  const leafClose = !!leaf?.box && leaf.leafFrac >= LEAF_MIN;
  const frameHint: Key | null = !leaf ? null
    : leaf.bright < BRIGHT_MIN ? "walk.photo.hint.dark"
      : !leaf.box ? "walk.photo.hint.no_leaf"
        : !leafClose ? "walk.photo.hint.closer"
          : leaf.sharp < SHARP_MIN || leaf.motion > STILL_MAX ? "walk.photo.hint.blurry" : "walk.photo.hint.ready";

  const sayText = t("walk.leaf.say", { name: field.farmer.name });
  useEffect(() => { if (step === "photo") speak(sayText); }, [step, sayText]);

  // Auto-capture: the leaf close, bright, steady and sharp for ~0.7 s takes the photo (or ~3 s steady at all);
  // the shutter still works by hand.
  const steady = useRef({ ready: 0, held: 0 });
  useEffect(() => {
    const s = steady.current;
    s.ready = frameHint === "walk.photo.hint.ready" ? s.ready + 1 : 0;
    s.held = leafClose && leaf!.motion <= STILL_MAX && leaf!.bright >= BRIGHT_MIN ? s.held + 1 : 0;
    if ((s.ready >= STEADY_CHECKS || s.held >= GIVE_UP_CHECKS) && step === "photo" && !busy) {
      steady.current = { ready: 0, held: 0 };
      void takePhoto();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaf]);

  // set synchronously: auto-capture can fire again before the busy state re-renders (seen on a real phone)
  const uploading = useRef(false);

  async function takePhoto(file?: Blob | null) {
    if (step !== "photo" || uploading.current) return;
    uploading.current = true;
    const v = cam.videoRef.current;
    const blob = file ?? (await cam.capture(leaf && v ? videoBox(leaf, v) : null));
    if (!blob) { uploading.current = false; fileRef.current?.click(); return; }
    setBusy(true);
    setStatus({ tone: "warn", text: t("walk.photo.checking") });
    try {
      // the photo is pinned to the flagged patch, not to wherever the phone is (the demo runs far from the field)
      const at = kase.target_cells[0]?.centre ?? patch[0];
      const photo = await api.uploadPhoto(kase.id, blob, {
        kind: "leaf_top", spot: 0, cell_id: kase.target_cells[0]?.id, lon: at[0], lat: at[1],
      });
      const retake = photo.vision.quality.retake_reason;
      if (retake) {
        const msg = t(retake === "dark" ? "walk.photo.dark" : "walk.photo.blurry");
        setStatus({ tone: "error", text: msg });
        speak(msg);
        return;
      }
      setStep("sending");
      await api.walk(kase.id, patch);
      setKase(await api.evidence(kase.id));
      setStep("done");
    } catch (e) {
      setStatus({ tone: "error", text: (e as Error).message });
      setStep("photo");
    } finally {
      uploading.current = false;
      setBusy(false);
    }
  }

  // the evidence may land from another tab (dashboard): keep the done screen current
  useEffect(() => {
    if (step !== "done" || kase.evidence) return;
    const id = setInterval(() => api.getCase(kase.id).then(setKase).catch(() => undefined), POLL_MS);
    return () => clearInterval(id);
  }, [step, kase.id, kase.evidence]);

  if (step === "done") return <Done kase={kase} />;

  return (
    <main className="walk walk-cam">
      <CameraGuide
        videoRef={cam.videoRef}
        cameraOn={cam.state === "on"}
        turnDeg={null}
        arrived
        leaf={step === "photo" ? leaf : null}
        top={
          <div className="cam-head">
            <p className="cam-title">{step === "photo" ? t("walk.leaf.title") : t("walk.sending")}</p>
            {step === "photo" && cam.state === "on" && (
              <p className={`cam-chip ${frameHint === "walk.photo.hint.ready" ? "" : "warn"}`} aria-live="polite">
                {frameHint ? t(frameHint) : t("walk.photo.auto")}
              </p>
            )}
            {step === "photo" && leaf?.box && (
              <p className="cam-chip num">{t("walk.photo.leaf_read", { y: leaf.yellowPct, b: leaf.brownPct })}</p>
            )}
            {cam.state === "denied" && <p className="cam-chip warn">{t("walk.camera_denied")}</p>}
          </div>
        }
      >
        {step === "photo" && (
          <>
            <p className="status-live" aria-live="polite">
              {status && <span className={`notice notice-${status.tone}`} style={{ display: "block" }}>{status.text}</span>}
            </p>
            <input ref={fileRef} id="photo-input" className="sr-only" type="file" accept="image/*" capture="environment"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void takePhoto(f); }} />
            <div className="row" style={{ gap: "var(--s-100)", justifyContent: "center", alignItems: "center" }}>
              <button type="button" className="btn btn-icon btn-glass" onClick={() => speak(sayText)} aria-label={t("common.play")}>
                <Volume2 aria-hidden="true" />
              </button>
              <button type="button" className={`shutter ${frameHint === "walk.photo.hint.ready" ? "shutter-ready" : ""}`} disabled={busy}
                onClick={() => void takePhoto()} aria-label={t("walk.photo.take")}>
                <span />
              </button>
            </div>
          </>
        )}
        {step === "sending" && <p className="cam-say" aria-live="polite">{t("walk.sending")}</p>}
      </CameraGuide>
    </main>
  );
}

/** After the photo: what was found, and a pointer back to the call, where the farmer presses 1, 2 or 3. */
function Done({ kase }: { kase: Case }) {
  const ev = kase.evidence;
  const level = ev?.problem_level ?? ev?.level ?? "medium";
  return (
    <main className="walk" aria-live="polite">
      <section className="panel stack" style={{ alignItems: "center", textAlign: "center" }}>
        <CheckCircle2 size={56} aria-hidden="true" color="var(--leaf-600)" />
        <h1 className="heading-4">{t("walk.done.title")}</h1>
        {ev ? (
          <>
            <p className="title-2">{t("ev.suspected", { cause: causeName(ev.cause) })}</p>
            <p className={`chip level-${level}`}>{t(`walk.done.level.${level}` as Key)}</p>
          </>
        ) : (
          <Skeleton height={60} />
        )}
        <p className="body-3"><Phone size={18} aria-hidden="true" /> {t("walk.done.listen")}</p>
      </section>
    </main>
  );
}
