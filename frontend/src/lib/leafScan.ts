import { type RefObject, useEffect, useState } from "react";

/**
 * Live leaf finder on the phone, a few times a second, no network:
 *  - plant pixels by colour (green to yellow hue, saturated enough), largest connected blob = the leaf
 *  - inside the leaf: yellow (mosaic / yellowing) and brown (spots, blight) patches, as a coarse grid for the overlay
 *  - sharpness of the leaf area (Laplacian variance on a 256 px crop, same measure as the server gate) and hand shake
 * This only frames and checks the photo. What the problem is comes from the server model.
 */
export type Box = { x: number; y: number; w: number; h: number };   // in scan pixels
export interface LeafScan {
  w: number; h: number;              // scan size (video aspect)
  box: Box | null;                   // the leaf
  leafFrac: number;                  // leaf share of the frame
  yellowPct: number; brownPct: number;
  cells: { x: number; y: number; kind: "yellow" | "brown" }[];   // CELL x CELL blocks for the overlay
  cell: number;
  sharp: number; bright: number; motion: number;
}

const SCAN_W = 160;
const CELL = 5;
const MIN_LEAF_FRAC = 0.04;

function hsv(r: number, g: number, b: number) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d) h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return { h: (h * 60 + 360) % 360, s: max ? d / max : 0, v: max };
}

export function scanFrame(px: Uint8ClampedArray, w: number, h: number): Omit<LeafScan, "sharp" | "motion"> {
  const n = w * h;
  const plant = new Uint8Array(n);       // 1 green, 2 yellow
  const brownish = new Uint8Array(n);
  let bright = 0;
  for (let i = 0; i < n; i++) {
    const { h: hue, s, v } = hsv(px[4 * i], px[4 * i + 1], px[4 * i + 2]);
    bright += v;
    // green needs little saturation (shade, dusty leaves); yellow must be strongly saturated, or a beige table,
    // khaki cloth or dry soil would pass as a yellowed leaf
    if (v > 35 && hue >= 68 && hue <= 170 && s > 0.18) plant[i] = 1;
    else if (v > 60 && hue >= 35 && hue < 68 && s > 0.45) plant[i] = 2;
    else if (v > 25 && v < 170 && s > 0.25 && hue >= 8 && hue < 35) brownish[i] = 1;
  }

  // largest 4-connected plant blob
  const label = new Int32Array(n).fill(-1);
  let best = -1, bestSize = 0;
  const stack: number[] = [];
  for (let start = 0; start < n; start++) {
    if (!plant[start] || label[start] !== -1) continue;
    let size = 0;
    label[start] = start; stack.push(start);
    while (stack.length) {
      const i = stack.pop()!; size++;
      const x = i % w;
      for (const j of [i - w, i + w, x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1]) {
        if (j >= 0 && j < n && plant[j] && label[j] === -1) { label[j] = start; stack.push(j); }
      }
    }
    if (size > bestSize) { bestSize = size; best = start; }
  }
  const leafFrac = bestSize / n;
  if (best < 0 || leafFrac < MIN_LEAF_FRAC) {
    return { w, h, box: null, leafFrac, yellowPct: 0, brownPct: 0, cells: [], cell: CELL, bright: bright / n };
  }

  // leaf extent per row and column: brown counts only inside the leaf, so a hand or soil next to it is ignored
  let x0 = w, y0 = h, x1 = 0, y1 = 0;
  const rowMin = new Int32Array(h).fill(w), rowMax = new Int32Array(h).fill(-1);
  const colMin = new Int32Array(w).fill(h), colMax = new Int32Array(w).fill(-1);
  for (let i = 0; i < n; i++) {
    if (label[i] !== best) continue;
    const x = i % w, y = (i / w) | 0;
    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
    rowMin[y] = Math.min(rowMin[y], x); rowMax[y] = Math.max(rowMax[y], x);
    colMin[x] = Math.min(colMin[x], y); colMax[x] = Math.max(colMax[x], y);
  }
  const inside = (i: number) => {
    const x = i % w, y = (i / w) | 0;
    return x > rowMin[y] && x < rowMax[y] && y > colMin[x] && y < colMax[x];
  };

  let yellow = 0, brown = 0, area = 0;
  const gw = Math.ceil(w / CELL), gh = Math.ceil(h / CELL);
  const gy = new Uint16Array(gw * gh), gb = new Uint16Array(gw * gh), ga = new Uint16Array(gw * gh);
  for (let i = 0; i < n; i++) {
    const own = label[i] === best;
    const isBrown = brownish[i] === 1 && inside(i);
    if (!own && !isBrown) continue;
    const g = (((i / w) | 0) / CELL | 0) * gw + ((i % w) / CELL | 0);
    area++; ga[g]++;
    if (own && plant[i] === 2) { yellow++; gy[g]++; }
    if (isBrown) { brown++; gb[g]++; }
  }
  const cells: LeafScan["cells"] = [];
  for (let g = 0; g < gw * gh; g++) {
    if (ga[g] < (CELL * CELL) / 3) continue;
    const kind = gb[g] / ga[g] > 0.35 ? "brown" : gy[g] / ga[g] > 0.45 ? "yellow" : null;
    if (kind) cells.push({ x: (g % gw) * CELL, y: ((g / gw) | 0) * CELL, kind });
  }
  return {
    w, h, box: { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 }, leafFrac,
    yellowPct: Math.round((100 * yellow) / area), brownPct: Math.round((100 * brown) / area),
    cells, cell: CELL, bright: bright / n,
  };
}

/** Laplacian variance of a grey image (same measure as backend vision.quality). */
function lapVar(px: Uint8ClampedArray, w: number, h: number) {
  const g = new Float32Array(w * h);
  for (let i = 0; i < g.length; i++) g[i] = 0.299 * px[4 * i] + 0.587 * px[4 * i + 1] + 0.114 * px[4 * i + 2];
  let n = 0, m = 0, m2 = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const lap = g[i - w] + g[i + w] + g[i - 1] + g[i + 1] - 4 * g[i];
      n++; m += lap; m2 += lap * lap;
    }
  }
  return n ? m2 / n - (m / n) ** 2 : 0;
}

/** Leaf box in video pixels, padded, for cropping the capture. */
export function videoBox(scan: LeafScan, video: HTMLVideoElement, pad = 0.12): Box | null {
  if (!scan.box) return null;
  const k = video.videoWidth / scan.w;
  const px = scan.box.w * pad, py = scan.box.h * pad;
  const x = Math.max(0, (scan.box.x - px) * k), y = Math.max(0, (scan.box.y - py) * k);
  return { x, y, w: Math.min(video.videoWidth - x, (scan.box.w + 2 * px) * k), h: Math.min(video.videoHeight - y, (scan.box.h + 2 * py) * k) };
}

export function useLeafScan(videoRef: RefObject<HTMLVideoElement | null>, active: boolean, everyMs = 220) {
  const [scan, setScan] = useState<LeafScan | null>(null);
  useEffect(() => {
    if (!active) { setScan(null); return; }
    const small = document.createElement("canvas");
    const sctx = small.getContext("2d", { willReadFrequently: true });
    const crop = document.createElement("canvas");
    crop.width = 256; crop.height = 256;
    const cctx = crop.getContext("2d", { willReadFrequently: true });
    let prev: Uint8ClampedArray | null = null;
    const id = setInterval(() => {
      const v = videoRef.current;
      if (!sctx || !cctx || !v || !v.videoWidth) return;
      const w = SCAN_W, h = Math.round((SCAN_W * v.videoHeight) / v.videoWidth);
      if (small.width !== w || small.height !== h) { small.width = w; small.height = h; prev = null; }
      sctx.drawImage(v, 0, 0, w, h);
      const px = sctx.getImageData(0, 0, w, h).data;
      let moved = 0;
      const hadPrev = prev !== null;
      if (prev) for (let i = 0; i < px.length; i += 4) moved += Math.abs(px[i + 1] - prev[i + 1]);
      prev = px.slice();
      const s = scanFrame(px, w, h);
      // sharpness on the leaf itself (or the whole frame when no leaf is found), at 256 px like the capture
      const k = v.videoWidth / w, b = s.box;
      if (b) cctx.drawImage(v, b.x * k, b.y * k, b.w * k, b.h * k, 0, 0, 256, 256);
      else cctx.drawImage(v, 0, 0, 256, 256);
      const sharp = lapVar(cctx.getImageData(0, 0, 256, 256).data, 256, 256);
      setScan({ ...s, sharp, motion: hadPrev ? moved / (w * h) : 99 });
    }, everyMs);
    return () => clearInterval(id);
  }, [videoRef, active, everyMs]);
  return scan;
}
