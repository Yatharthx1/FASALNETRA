import { useEffect, useRef, useState } from "react";
import type { LonLat } from "./geo";

/**
 * Position every 200 ms for the AR walk. Phone GPS chips give about one fix a second and browsers cannot ask for
 * more, so between fixes the position is carried forward by counted footsteps (accelerometer) along the compass
 * heading, and each GPS fix pulls it back in proportion to how much it can be trusted (a 1-D Kalman filter per
 * axis, in metres east / north of the first fix). Result: a red line that moves smoothly with the farmer instead
 * of jumping once a second, and less GPS wander when standing still.
 */
export const TICK_MS = 200;
const STRIDE_M = 0.65;              // typical step in a field
const STEP_VAR_M2 = 1.0 ** 2;       // per step: stride and heading error (tuned on a simulated 1 Hz, 5 m-noise walk)
const IDLE_VAR_M2_PER_S = 0.05;     // drift while standing
const OUTLIER_SIGMA = 4;            // a GPS jump this far outside the expected error is mostly ignored
const M_PER_DEG_LAT = 110540;

export interface Sample {
  t: number;                        // ms since epoch
  pos: LonLat;
  accuracy: number;                 // metres, 1 sigma
  heading: number | null;           // degrees from north
  speed: number;                    // m/s over the last second
  source: "gps" | "steps" | "hold";
  gpsAge: number | null;            // ms since the last real fix
}

export interface GpsFix { t: number; pos: LonLat; accuracy: number; course: number | null }

export function createFuser() {
  let origin: LonLat | null = null;
  let x = 0, y = 0, v = 0;           // metres east / north of origin, variance m^2
  let pendingSteps = 0;
  let lastTick = 0, lastFix: number | null = null;
  let heading: number | null = null;
  const recent: { t: number; x: number; y: number }[] = [];

  const toLocal = (p: LonLat) => {
    const mLon = 111320 * Math.cos((origin![1] * Math.PI) / 180);
    return { x: (p[0] - origin![0]) * mLon, y: (p[1] - origin![1]) * M_PER_DEG_LAT };
  };
  const toLonLat = (lx: number, ly: number): LonLat => {
    const mLon = 111320 * Math.cos((origin![1] * Math.PI) / 180);
    return [origin![0] + lx / mLon, origin![1] + ly / M_PER_DEG_LAT];
  };

  return {
    /** One detected footstep. */
    step() { pendingSteps++; },
    /** Compass (or other) heading in degrees; null when unknown. */
    setHeading(h: number | null) { heading = h; },
    /** A real GPS fix: correct the estimate. */
    gps(fix: GpsFix) {
      const r = Math.max(fix.accuracy, 3) ** 2;
      if (!origin) { origin = fix.pos; x = 0; y = 0; v = r; lastFix = fix.t; return; }
      const z = toLocal(fix.pos);
      const dx = z.x - x, dy = z.y - y;
      const gate = OUTLIER_SIGMA * Math.sqrt(v + r);
      // a jump far outside the expected error (multipath under trees, a bad fix) only nudges the estimate
      const rEff = Math.hypot(dx, dy) > gate ? r * 25 : r;
      const k = v / (v + rEff);
      x += k * dx; y += k * dy; v = (1 - k) * v;
      if (heading === null && fix.course !== null) heading = fix.course;
      lastFix = fix.t;
    },
    /** Called every TICK_MS: carry the estimate forward by the steps taken since the last tick. */
    tick(t: number): Sample | null {
      if (!origin) return null;
      const dt = lastTick ? (t - lastTick) / 1000 : 0;
      lastTick = t;
      let source: Sample["source"] = lastFix !== null && t - lastFix < TICK_MS * 1.5 ? "gps" : "hold";
      if (pendingSteps && heading !== null) {
        const a = (heading * Math.PI) / 180, d = pendingSteps * STRIDE_M;
        x += d * Math.sin(a); y += d * Math.cos(a);
        v += pendingSteps * STEP_VAR_M2;
        source = "steps";
      } else {
        v += IDLE_VAR_M2_PER_S * dt;
      }
      pendingSteps = 0;
      recent.push({ t, x, y });
      while (recent.length && t - recent[0].t > 1000) recent.shift();
      const first = recent[0];
      const speed = first && t > first.t ? Math.hypot(x - first.x, y - first.y) / ((t - first.t) / 1000) : 0;
      return { t, pos: toLonLat(x, y), accuracy: Math.sqrt(v), heading, speed, source,
               gpsAge: lastFix === null ? null : t - lastFix };
    },
  };
}

/** Footsteps from the accelerometer: peaks of the gravity-included magnitude, at most ~3 a second. */
export function createStepDetector(onStep: () => void) {
  let avg = 9.81, rising = false, last = 0;
  const THRESH = 1.2, MIN_GAP_MS = 300;
  return (magnitude: number, t: number) => {
    avg = 0.98 * avg + 0.02 * magnitude;          // slow baseline (gravity)
    const above = magnitude > avg + THRESH;
    if (above && !rising && t - last > MIN_GAP_MS) { last = t; onStep(); }
    rising = above;
  };
}

/** Fused position every 200 ms while `active`. `onSample` gets every sample (for upload). */
export function useFusedPosition(active: boolean, compass: number | null, onSample?: (s: Sample) => void) {
  const [sample, setSample] = useState<Sample | null>(null);
  const [denied, setDenied] = useState(false);
  const fuser = useRef(createFuser());
  const cb = useRef(onSample);
  cb.current = onSample;

  useEffect(() => { fuser.current.setHeading(compass); }, [compass]);

  useEffect(() => {
    if (!active) return;
    const f = fuser.current;
    const geo = "geolocation" in navigator ? navigator.geolocation.watchPosition(
      (p) => f.gps({ t: p.timestamp || Date.now(), pos: [p.coords.longitude, p.coords.latitude],
                     accuracy: p.coords.accuracy, course: Number.isFinite(p.coords.heading) ? p.coords.heading : null }),
      (e) => setDenied(e.code === e.PERMISSION_DENIED),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 },
    ) : null;
    const detect = createStepDetector(() => f.step());
    const onMotion = (e: DeviceMotionEvent) => {
      const a = e.accelerationIncludingGravity;
      if (a && a.x !== null && a.y !== null && a.z !== null) detect(Math.hypot(a.x, a.y, a.z), Date.now());
    };
    window.addEventListener("devicemotion", onMotion);
    const id = setInterval(() => {
      const s = f.tick(Date.now());
      if (s) { setSample(s); cb.current?.(s); }
    }, TICK_MS);
    return () => {
      if (geo !== null) navigator.geolocation.clearWatch(geo);
      window.removeEventListener("devicemotion", onMotion);
      clearInterval(id);
    };
  }, [active]);

  return { sample, denied };
}

/** Collects samples and sends them in batches (default every 2 s): 5 packets a second, one request. */
export function createTrackUploader(send: (batch: Sample[]) => Promise<unknown>, everyMs = 2000, maxKeep = 900) {
  let buf: Sample[] = [];
  let inFlight = false;
  const flush = async () => {
    if (inFlight || !buf.length || !navigator.onLine) return;
    const batch = buf; buf = [];
    inFlight = true;
    try { await send(batch); } catch { buf = [...batch, ...buf].slice(-maxKeep); } finally { inFlight = false; }
  };
  const id = setInterval(() => void flush(), everyMs);
  return { push: (s: Sample) => { buf.push(s); if (buf.length > maxKeep) buf = buf.slice(-maxKeep); },
           flush, stop: () => { clearInterval(id); void flush(); } };
}
