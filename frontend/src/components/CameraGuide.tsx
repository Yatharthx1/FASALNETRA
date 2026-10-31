import type { ReactNode, RefObject } from "react";

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraOn: boolean;
  /** Signed turn to the target in degrees (+ = right); null when the phone cannot tell its heading. */
  turnDeg: number | null;
  arrived: boolean;
  top: ReactNode;
  inset?: ReactNode;
  children?: ReactNode;
}

const VB_W = 100, VB_H = 160;

/** Red walking line drawn on the live camera: a ribbon that narrows with distance and bends towards the target. */
function ribbon(turnDeg: number) {
  const a = (Math.max(-75, Math.min(75, turnDeg)) * Math.PI) / 180;
  const p0 = { x: 50, y: VB_H }, p1 = { x: 50, y: VB_H - 45 };
  const p2 = { x: 50 + 44 * Math.sin(a), y: VB_H - 45 - 62 * Math.cos(a) };
  const left: string[] = [], right: string[] = [], centre: string[] = [];
  const chevrons: string[] = [];
  const N = 28;
  for (let i = 0; i <= N; i++) {
    const t = i / N, u = 1 - t;
    const x = u * u * p0.x + 2 * u * t * p1.x + t * t * p2.x;
    const y = u * u * p0.y + 2 * u * t * p1.y + t * t * p2.y;
    const dx = 2 * u * (p1.x - p0.x) + 2 * t * (p2.x - p1.x);
    const dy = 2 * u * (p1.y - p0.y) + 2 * t * (p2.y - p1.y);
    const len = Math.hypot(dx, dy) || 1, nx = -dy / len, ny = dx / len;
    const w = 13 * (1 - t) + 1.5;                       // perspective: wide at the feet, thin at the horizon
    left.push(`${x + nx * w},${y + ny * w}`);
    right.unshift(`${x - nx * w},${y - ny * w}`);
    centre.push(`${x},${y}`);
    if (i === 8 || i === 15 || i === 21) {
      const s = w * 0.55, fx = dx / len, fy = dy / len;
      chevrons.push(`M${x - nx * s - fx * s * 0.6},${y - ny * s - fy * s * 0.6} L${x + fx * s * 0.4},${y + fy * s * 0.4} L${x + nx * s - fx * s * 0.6},${y + ny * s - fy * s * 0.6}`);
    }
  }
  return { body: [...left, ...right].join(" "), centre: centre.join(" "), chevrons, end: p2 };
}

export default function CameraGuide({ videoRef, cameraOn, turnDeg, arrived, top, inset, children }: Props) {
  const back = turnDeg !== null && Math.abs(turnDeg) > 110;
  const r = ribbon(turnDeg ?? 0);
  return (
    <div className="cam">
      {/* Live rear camera; without a camera (laptop demo) a field-coloured backdrop keeps the guide readable. */}
      <video ref={videoRef} className="cam-video" playsInline muted autoPlay aria-hidden="true" style={{ opacity: cameraOn ? 1 : 0 }} />
      {!cameraOn && <div className="cam-fallback" aria-hidden="true" />}

      <svg className="cam-overlay" viewBox={`0 0 ${VB_W} ${VB_H}`} preserveAspectRatio="none" aria-hidden="true">
        {!back && !arrived && (
          <g className="cam-line">
            <polygon points={r.body} fill="#C62E1F" fillOpacity="0.72" stroke="#FFFDF8" strokeWidth="0.6" strokeOpacity="0.8" />
            <polyline points={r.centre} fill="none" stroke="#FFFDF8" strokeWidth="0.9" strokeDasharray="2 3" strokeLinecap="round" />
            {r.chevrons.map((d, i) => <path key={i} d={d} fill="none" stroke="#FFFDF8" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />)}
            <circle cx={r.end.x} cy={r.end.y} r="3.2" fill="#FFFDF8" stroke="#C62E1F" strokeWidth="1.4" />
          </g>
        )}
        {arrived && (
          <g>
            <ellipse cx="50" cy="128" rx="30" ry="10" fill="#2F7A4A" fillOpacity="0.55" stroke="#FFFDF8" strokeWidth="0.8" />
            <ellipse cx="50" cy="128" rx="30" ry="10" fill="none" stroke="#FFFDF8" strokeWidth="0.6" strokeDasharray="2 2" />
          </g>
        )}
      </svg>

      {back && !arrived && (
        <div className="cam-back" aria-hidden="true">
          <svg width="96" height="96" viewBox="0 0 48 48"><path d="M34 40 V20 C34 12 28 8 22 8 C15 8 10 13 10 20 V26" fill="none" stroke="#FFFDF8" strokeWidth="5" strokeLinecap="round" /><path d="M3 21 L10 29 L17 21" fill="none" stroke="#FFFDF8" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
      )}

      <div className="cam-top">{top}</div>
      {inset && <div className="cam-inset">{inset}</div>}
      <div className="cam-bottom">{children}</div>
    </div>
  );
}
