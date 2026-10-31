export type LonLat = [number, number];

const R = 6371000;
const rad = Math.PI / 180;

export function metres(a: LonLat, b: LonLat): number {
  const dLat = (b[1] - a[1]) * rad, dLon = (b[0] - a[0]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Compass bearing from a to b, degrees clockwise from north. */
export function bearing(a: LonLat, b: LonLat): number {
  const y = Math.sin((b[0] - a[0]) * rad) * Math.cos(b[1] * rad);
  const x = Math.cos(a[1] * rad) * Math.sin(b[1] * rad) - Math.sin(a[1] * rad) * Math.cos(b[1] * rad) * Math.cos((b[0] - a[0]) * rad);
  return (Math.atan2(y, x) / rad + 360) % 360;
}

/** Signed turn from heading to target bearing, -180..180 (positive = turn right). */
export function turn(heading: number, target: number): number {
  return ((target - heading + 540) % 360) - 180;
}

/** Point `m` metres from a towards b (for the demo walk). */
export function stepTowards(a: LonLat, b: LonLat, m: number): LonLat {
  const d = metres(a, b);
  if (d <= m) return b;
  const k = m / d;
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];
}

export function polygonAcres(ring: LonLat[]): number {
  if (ring.length < 3) return 0;
  const lat0 = ring[0][1] * rad, mLon = 111320 * Math.cos(lat0), mLat = 110540;
  let s = 0;
  ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length];
    s += p[0] * mLon * q[1] * mLat - q[0] * mLon * p[1] * mLat;
  });
  return Math.abs(s) / 2 / 4046.86;
}
