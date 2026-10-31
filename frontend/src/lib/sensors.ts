import { useEffect, useRef, useState } from "react";
import { bearing, metres, type LonLat } from "./geo";

/** Rear camera stream. Needs a secure origin (https or localhost). */
export function useCamera(active: boolean) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<"off" | "starting" | "on" | "denied" | "unavailable">("off");

  useEffect(() => {
    if (!active) return;
    if (!navigator.mediaDevices?.getUserMedia) { setState("unavailable"); return; }
    let stream: MediaStream | null = null;
    let cancelled = false;
    setState("starting");
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } }, audio: false })
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; }
        stream = s;
        if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => undefined); }
        setState("on");
      })
      .catch((e: DOMException) => setState(e.name === "NotAllowedError" ? "denied" : "unavailable"));
    return () => { cancelled = true; stream?.getTracks().forEach((t) => t.stop()); };
  }, [active]);

  /** Current frame as a JPEG. */
  const capture = async (): Promise<Blob | null> => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return null;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0);
    return new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
  };

  return { videoRef, state, capture };
}

export type Fix = { pos: LonLat; accuracy: number; course: number | null };

/** GPS with course over ground (heading from the last two fixes when moving). */
export function useGps(active: boolean) {
  const [fix, setFix] = useState<Fix | null>(null);
  const [denied, setDenied] = useState(false);
  const last = useRef<LonLat | null>(null);
  useEffect(() => {
    if (!active || !("geolocation" in navigator)) return;
    const id = navigator.geolocation.watchPosition(
      (p) => {
        const pos: LonLat = [p.coords.longitude, p.coords.latitude];
        let course = p.coords.heading ?? null;
        if (course === null && last.current && metres(last.current, pos) > 2) course = bearing(last.current, pos);
        if (!last.current || metres(last.current, pos) > 2) last.current = pos;
        setFix({ pos, accuracy: p.coords.accuracy, course: Number.isFinite(course as number) ? course : null });
      },
      (e) => setDenied(e.code === e.PERMISSION_DENIED),
      { enableHighAccuracy: true, maximumAge: 1000, timeout: 15000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [active]);
  return { fix, denied };
}

/** Compass heading of the phone's back camera, if the device has one. */
export function useHeading(active: boolean) {
  const [heading, setHeading] = useState<number | null>(null);
  useEffect(() => {
    if (!active) return;
    const onOrient = (e: DeviceOrientationEvent & { webkitCompassHeading?: number }) => {
      if (typeof e.webkitCompassHeading === "number") setHeading(e.webkitCompassHeading);
      else if (e.absolute && e.alpha !== null) setHeading((360 - e.alpha) % 360);
    };
    const ev = "ondeviceorientationabsolute" in window ? "deviceorientationabsolute" : "deviceorientation";
    window.addEventListener(ev, onOrient as EventListener, true);
    return () => window.removeEventListener(ev, onOrient as EventListener, true);
  }, [active]);
  return heading;
}

/** iOS asks for motion permission from a user tap. */
export async function askMotionPermission() {
  const D = DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> };
  if (typeof D.requestPermission === "function") {
    try { await D.requestPermission(); } catch { /* user said no: course over ground is used instead */ }
  }
}
