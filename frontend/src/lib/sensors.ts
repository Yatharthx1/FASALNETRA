import { useEffect, useRef, useState } from "react";

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

  /** A JPEG, at most 1024 px a side (the server reads no more): ~150 KB instead of ~1 MB on 2G/3G.
   * With a crop (the leaf's box, in video pixels) only that part is sent, at most 768 px: ~50 KB.
   * Where the phone supports it (Chrome on Android) a real still photo is taken: it autofocuses and is much sharper
   * than a frame of the compressed video stream. Otherwise, or if that fails, the current video frame is used. */
  const capture = async (crop?: { x: number; y: number; w: number; h: number } | null): Promise<Blob | null> => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return null;
    const still = await stillPhoto(v);
    const img: CanvasImageSource = still ?? v;
    const k = still ? still.width / v.videoWidth : 1;    // still photos are larger than the video frames
    const box = crop ?? { x: 0, y: 0, w: v.videoWidth, h: v.videoHeight };
    const src = { x: box.x * k, y: box.y * k, w: box.w * k, h: box.h * k };
    const scale = Math.min(1, (crop ? CROP_MAX_SIDE : CAPTURE_MAX_SIDE) / Math.max(src.w, src.h));
    const c = document.createElement("canvas");
    c.width = Math.round(src.w * scale); c.height = Math.round(src.h * scale);
    c.getContext("2d")!.drawImage(img, src.x, src.y, src.w, src.h, 0, 0, c.width, c.height);
    still?.close();
    return new Promise((r) => c.toBlob(r, "image/jpeg", 0.85));
  };

  return { videoRef, state, capture };
}

const CAPTURE_MAX_SIDE = 1024;
const STILL_TIMEOUT_MS = 2500;   // a phone that hangs on takePhoto falls back to the video frame

type ImageCaptureLike = { takePhoto(): Promise<Blob> };
declare const ImageCapture: { new (track: MediaStreamTrack): ImageCaptureLike } | undefined;

async function stillPhoto(v: HTMLVideoElement): Promise<ImageBitmap | null> {
  const track = (v.srcObject as MediaStream | null)?.getVideoTracks()[0];
  if (!track || typeof ImageCapture === "undefined") return null;
  try {
    const shot = new ImageCapture(track).takePhoto();
    const timeout = new Promise<null>((r) => setTimeout(() => r(null), STILL_TIMEOUT_MS));
    const blob = await Promise.race([shot, timeout]);
    if (!blob) return null;
    const bmp = await createImageBitmap(blob);
    // some phones return the still rotated relative to the video: then the crop would miss the leaf
    if ((bmp.width > bmp.height) !== (v.videoWidth > v.videoHeight)) { bmp.close(); return null; }
    return bmp;
  } catch {
    return null;
  }
}
const CROP_MAX_SIDE = 768;
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
  // compass (orientation) and step counting (motion) are separate permissions on iOS
  for (const E of [DeviceOrientationEvent, DeviceMotionEvent] as unknown as { requestPermission?: () => Promise<string> }[]) {
    if (typeof E?.requestPermission === "function") {
      try { await E.requestPermission(); } catch { /* user said no: GPS alone is used instead */ }
    }
  }
}
