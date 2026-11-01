import { useMemo } from "react";
import type { Geometry, MultiPolygon, Polygon } from "geojson";

export interface AnimatedFieldGraphicProps {
  field: Polygon;
  zone?: Geometry | null;
  trail?: [number, number][];
  khasra?: string;
  fieldAcres?: number;
  patchAcres?: number;
}

interface Point2D {
  x: number;
  y: number;
}

const SVG_WIDTH = 800;
const SVG_HEIGHT = 480;
const PADDING = 60;

export default function AnimatedFieldGraphic({
  field,
  zone,
  trail = [],
  khasra,
  fieldAcres,
  patchAcres,
}: AnimatedFieldGraphicProps) {
  // Extract and project geometries into conformal 2D Cartesian coordinates (meters)
  // Conformal Equirectangular Projection preserves 100% of physical polygon angles and proportions.
  const {
    fieldPath,
    zonePaths,
    trailPath,
    trailPoints,
    zoneCentroid,
    scaleMeters,
    scalePixels,
  } = useMemo(() => {
    const fieldCoords = field.coordinates[0] || [];
    if (fieldCoords.length < 3) {
      return {
        fieldPath: "",
        zonePaths: [],
        trailPath: "",
        trailPoints: [],
        zoneCentroid: null,
        scaleMeters: 50,
        scalePixels: 100,
      };
    }

    // 1. Calculate reference mean latitude to get accurate metric longitude scale
    const allLats = fieldCoords.map((c) => c[1]);
    const meanLat = allLats.reduce((a, b) => a + b, 0) / allLats.length;
    const cosLat = Math.cos((meanLat * Math.PI) / 180);

    // Standard WGS84 geodesic constants at reference latitude
    const METERS_PER_DEG_LON = 111320 * cosLat;
    const METERS_PER_DEG_LAT = 110540;

    // Convert (lon, lat) to local Cartesian coordinates in meters.
    // Notice: -lat * METERS_PER_DEG_LAT ensures North (increasing latitude) points UPWARDS in Cartesian (Y+ = North).
    const toMeters = (lon: number, lat: number): Point2D => ({
      x: lon * METERS_PER_DEG_LON,
      y: -lat * METERS_PER_DEG_LAT,
    });

    const fieldMeters = fieldCoords.map((c) => toMeters(c[0], c[1]));

    // 2. Bounding Box of the field in meters
    const xs = fieldMeters.map((p) => p.x);
    const ys = fieldMeters.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);

    // 3. UNIFORM SCALE: Must be identical for both X and Y to preserve 100% of polygon angles!
    const availableWidth = SVG_WIDTH - PADDING * 2;
    const availableHeight = SVG_HEIGHT - PADDING * 2;
    const scale = Math.min(availableWidth / spanX, availableHeight / spanY);

    // Center the field in the SVG viewport
    const contentWidth = spanX * scale;
    const contentHeight = spanY * scale;
    const offsetX = PADDING + (availableWidth - contentWidth) / 2;
    const offsetY = PADDING + (availableHeight - contentHeight) / 2;

    // Transform metric Cartesian coordinates into SVG pixel coordinates
    // (Cartesian Y+ goes up, SVG Y+ goes down, so we subtract Y offset)
    const toSvg = (m: Point2D): Point2D => ({
      x: offsetX + (m.x - minX) * scale,
      y: offsetY + (m.y - minY) * scale,
    });

    const toSvgPath = (coords: number[][]): string => {
      if (coords.length < 2) return "";
      const pts = coords.map((c) => toSvg(toMeters(c[0], c[1])));
      return pts.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`, "") + " Z";
    };

    // Projected field polygon SVG path
    const fieldPathD = toSvgPath(fieldCoords);

    // Projected zone (sick patch) SVG paths
    const zPaths: string[] = [];
    let zCentroid: Point2D | null = null;

    if (zone) {
      if (zone.type === "Polygon") {
        const poly = zone as Polygon;
        if (poly.coordinates?.[0]?.length) {
          zPaths.push(toSvgPath(poly.coordinates[0]));
          // Calculate centroid of the zone
          const pts = poly.coordinates[0].map((c) => toSvg(toMeters(c[0], c[1])));
          const cx = pts.reduce((sum, p) => sum + p.x, 0) / pts.length;
          const cy = pts.reduce((sum, p) => sum + p.y, 0) / pts.length;
          zCentroid = { x: cx, y: cy };
        }
      } else if (zone.type === "MultiPolygon") {
        const mpoly = zone as MultiPolygon;
        mpoly.coordinates.forEach((poly) => {
          if (poly?.[0]?.length) {
            zPaths.push(toSvgPath(poly[0]));
          }
        });
      }
    }

    // Projected walk trail
    let trPath = "";
    const trPoints: Point2D[] = [];
    if (trail && trail.length > 1) {
      const pts = trail.map((c) => toSvg(toMeters(c[0], c[1])));
      trPoints.push(...pts);
      trPath = pts.reduce((acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`, "");
    }

    // Scale bar calculation: 50 meters in pixels
    const sMeters = spanX > 200 ? 50 : 25;
    const sPixels = sMeters * scale;

    return {
      fieldPath: fieldPathD,
      zonePaths: zPaths,
      trailPath: trPath,
      trailPoints: trPoints,
      zoneCentroid: zCentroid,
      scaleMeters: sMeters,
      scalePixels: sPixels,
    };
  }, [field, zone, trail]);

  return (
    <div className="animated-field-container" style={{ position: "relative", width: "100%", height: "100%", minHeight: 420 }}>
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        className="animated-field-svg"
        style={{
          width: "100%",
          height: "100%",
          display: "block",
          background: "linear-gradient(145deg, #0d140e 0%, #151d16 50%, #0d130e 100%)",
          borderRadius: "var(--r-xl)",
          overflow: "hidden",
        }}
        aria-label="Animated agricultural field boundary and sick patch"
      >
        <defs>
          {/* Subtle agricultural grid pattern */}
          <pattern id="agriGrid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1" />
            <circle cx="20" cy="20" r="1" fill="rgba(74, 222, 128, 0.15)" />
          </pattern>

          {/* Internal crop row texture */}
          <pattern id="cropRows" width="16" height="16" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="16" stroke="rgba(74, 222, 128, 0.12)" strokeWidth="2" />
          </pattern>

          {/* Warning hatch pattern for the sick patch */}
          <pattern id="sickHatch" width="12" height="12" patternTransform="rotate(-45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="12" stroke="rgba(239, 68, 68, 0.45)" strokeWidth="3" />
          </pattern>

          {/* Glowing filter for the affected zone */}
          <filter id="patchGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* High-tech scanning gradient */}
          <linearGradient id="scanBeam" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(74, 222, 128, 0)" />
            <stop offset="50%" stopColor="rgba(74, 222, 128, 0.35)" />
            <stop offset="100%" stopColor="rgba(74, 222, 128, 0)" />
          </linearGradient>

          {/* Clip path to restrict scan beam to the exact field polygon */}
          <clipPath id="fieldClip">
            <path d={fieldPath} />
          </clipPath>
        </defs>

        {/* 1. Background Grid */}
        <rect width="100%" height="100%" fill="url(#agriGrid)" />

        {/* 2. Farmer's Field Polygon (True Angle & Shape) */}
        {fieldPath && (
          <g className="field-group">
            {/* Field interior fill with crop rows */}
            <path d={fieldPath} fill="rgba(34, 197, 94, 0.08)" stroke="none" />
            <path d={fieldPath} fill="url(#cropRows)" stroke="none" />

            {/* High-visibility field boundary */}
            <path
              d={fieldPath}
              fill="none"
              stroke="#4ade80"
              strokeWidth="3.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              style={{ filter: "drop-shadow(0 0 6px rgba(74, 222, 128, 0.4))" }}
            />

            {/* Subtle inner boundary glow line */}
            <path
              d={fieldPath}
              fill="none"
              stroke="rgba(255, 255, 255, 0.6)"
              strokeWidth="1"
              strokeDasharray="8 6"
              strokeLinejoin="round"
            />
          </g>
        )}

        {/* 3. Animated Scanner Beam sweeping across the field */}
        {fieldPath && (
          <g clipPath="url(#fieldClip)">
            <rect x="0" y="0" width={SVG_WIDTH} height="80" fill="url(#scanBeam)">
              <animate
                attributeName="y"
                from="-100"
                to={SVG_HEIGHT + 100}
                dur="4.5s"
                repeatCount="indefinite"
              />
            </rect>
          </g>
        )}

        {/* 4. The Affected Sick Patch (Mapped from Farmer's Web Session) */}
        {zonePaths.map((d, idx) => (
          <g key={`zone-${idx}`} className="sick-zone-group">
            {/* Continuous pulsing aura glow around the sick patch */}
            <path
              d={d}
              fill="rgba(239, 68, 68, 0.25)"
              stroke="#ef4444"
              strokeWidth="4"
              strokeLinejoin="round"
              style={{
                filter: "url(#patchGlow)",
                animation: "patchBreathe 2.4s ease-in-out infinite",
              }}
            />

            {/* Warning hatch overlay inside the sick patch */}
            <path d={d} fill="url(#sickHatch)" stroke="none" opacity="0.8" />

            {/* Animated marching dashed perimeter */}
            <path
              d={d}
              fill="none"
              stroke="#fca5a5"
              strokeWidth="2"
              strokeDasharray="6 4"
              strokeLinejoin="round"
              style={{
                animation: "dashMarch 15s linear infinite",
              }}
            />
          </g>
        ))}

        {/* 5. Farmer's Walk Trail from Web Session */}
        {trailPath && (
          <g className="farmer-trail-group">
            <path
              d={trailPath}
              fill="none"
              stroke="#fbbf24"
              strokeWidth="3"
              strokeDasharray="5 3"
              strokeLinecap="round"
              style={{
                filter: "drop-shadow(0 0 4px rgba(251, 191, 36, 0.7))",
                animation: "dashMarchReverse 10s linear infinite",
              }}
            />
            {trailPoints.map((p, i) => (
              <circle
                key={`tr-${i}`}
                cx={p.x}
                cy={p.y}
                r="3"
                fill="#fbbf24"
                stroke="#78350f"
                strokeWidth="1"
              />
            ))}
          </g>
        )}

        {/* 6. Centroid Radar Ping on Sick Patch */}
        {zoneCentroid && (
          <g transform={`translate(${zoneCentroid.x}, ${zoneCentroid.y})`}>
            {/* Expanding ripple rings */}
            <circle cx="0" cy="0" r="10" fill="none" stroke="#ef4444" strokeWidth="2" opacity="0.8">
              <animate attributeName="r" values="8; 36" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.9; 0" dur="2s" repeatCount="indefinite" />
            </circle>
            <circle cx="0" cy="0" r="10" fill="none" stroke="#f97316" strokeWidth="1.5" opacity="0.6">
              <animate attributeName="r" values="8; 26" dur="2s" begin="0.6s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.8; 0" dur="2s" begin="0.6s" repeatCount="indefinite" />
            </circle>

            {/* Central Warning Core */}
            <circle cx="0" cy="0" r="6" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />

            {/* Target Label Callout */}
            <g transform="translate(14, -14)">
              <rect
                x="0"
                y="-18"
                width="140"
                height="24"
                rx="6"
                fill="rgba(24, 24, 27, 0.9)"
                stroke="#ef4444"
                strokeWidth="1.5"
              />
              <text
                x="70"
                y="-2"
                fill="#ffffff"
                fontSize="11"
                fontWeight="700"
                textAnchor="middle"
                fontFamily="system-ui, sans-serif"
              >
                ⚠️ SICK PATCH {patchAcres ? `(${patchAcres} A)` : ""}
              </text>
            </g>
          </g>
        )}

        {/* 7. Orientation Compass (North Arrow) */}
        <g transform={`translate(${SVG_WIDTH - 54}, 50)`} className="compass-rose">
          <circle cx="0" cy="0" r="22" fill="rgba(15, 23, 42, 0.75)" stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1.5" />
          {/* North pointing triangle */}
          <polygon points="0,-16 5,0 0,-4 -5,0" fill="#ef4444" />
          {/* South pointing triangle */}
          <polygon points="0,16 5,0 0,4 -5,0" fill="rgba(255, 255, 255, 0.4)" />
          <text x="0" y="-20" fill="#ef4444" fontSize="12" fontWeight="800" textAnchor="middle" fontFamily="sans-serif">
            N
          </text>
        </g>

        {/* 8. Scale Bar (Bottom Left) */}
        <g transform={`translate(40, ${SVG_HEIGHT - 32})`} className="scale-bar">
          <rect x="0" y="0" width={scalePixels} height="4" fill="#ffffff" rx="1" />
          <line x1="0" y1="-3" x2="0" y2="7" stroke="#ffffff" strokeWidth="2" />
          <line x1={scalePixels} y1="-3" x2={scalePixels} y2="7" stroke="#ffffff" strokeWidth="2" />
          <text
            x={scalePixels / 2}
            y="-6"
            fill="rgba(255, 255, 255, 0.85)"
            fontSize="11"
            fontWeight="600"
            textAnchor="middle"
            fontFamily="sans-serif"
          >
            {scaleMeters} m
          </text>
        </g>

        {/* 9. Parcel & Status Badge (Top Left) */}
        <g transform="translate(36, 42)">
          <rect
            x="0"
            y="-18"
            width="170"
            height="30"
            rx="8"
            fill="rgba(15, 23, 42, 0.85)"
            stroke="rgba(74, 222, 128, 0.4)"
            strokeWidth="1.5"
          />
          <text x="12" y="2" fill="#4ade80" fontSize="13" fontWeight="700" fontFamily="sans-serif">
            {khasra ? `Khasra ${khasra}` : "Field Polygon"}
          </text>
          <text x="100" y="2" fill="rgba(255, 255, 255, 0.7)" fontSize="12" fontWeight="500" fontFamily="sans-serif">
            {fieldAcres ? `· ${fieldAcres} A` : ""}
          </text>
        </g>
      </svg>

      {/* Animation Styles */}
      <style>{`
        @keyframes patchBreathe {
          0%, 100% {
            opacity: 0.65;
            transform: scale(1);
          }
          50% {
            opacity: 0.95;
            transform: scale(1.008);
          }
        }
        @keyframes dashMarch {
          to {
            stroke-dashoffset: -100;
          }
        }
        @keyframes dashMarchReverse {
          to {
            stroke-dashoffset: 100;
          }
        }
      `}</style>
    </div>
  );
}
