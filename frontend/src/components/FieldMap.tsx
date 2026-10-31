import "leaflet/dist/leaflet.css";
import { useEffect, useMemo } from "react";
import { CircleMarker, GeoJSON, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import type { Geometry, LineString, Polygon } from "geojson";
import type { GridCell, TargetCell } from "../types/api";

const SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const COLORS = { field: "#fbf8f3", flagged: "#c2410c", target: "#c2410c", zone: "#c2410c", route: "#fde047", me: "#1d4ed8" };

function FitTo({ geometry, pad = 24 }: { geometry: Geometry; pad?: number }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(L.geoJSON(geometry as never).getBounds(), { padding: [pad, pad], maxZoom: 19 });
  }, [map, geometry, pad]);
  return null;
}

export interface FieldMapProps {
  field: Polygon;
  cells?: GridCell[];
  targets?: TargetCell[];
  activeTarget?: string;
  zone?: Geometry | null;
  trail?: [number, number][];
  route?: LineString | null;
  drone?: [number, number] | null;
  me?: [number, number] | null;
  neighbours?: Geometry[];
  /** Part of the route already sprayed, drawn solid over the dashed plan. */
  sprayed?: [number, number][];
  /** Small inset map: no extra padding when fitting. */
  compact?: boolean;
  label: string;
}

/** Satellite map with the field, its 10 m grid, the farmer's position, the zone and the spray route. */
export default function FieldMap({ field, cells = [], targets = [], activeTarget, zone, trail = [], route, drone, me, neighbours = [], sprayed, compact, label }: FieldMapProps) {
  const flagged = useMemo(() => cells.filter((c) => c.flagged), [cells]);
  const healthy = useMemo(() => cells.filter((c) => !c.flagged), [cells]);
  const latlng = (p: [number, number]) => [p[1], p[0]] as [number, number];

  return (
    <MapContainer center={[24.1036, 75.1218]} zoom={18} maxZoom={20} style={{ height: "100%", width: "100%" }}
      attributionControl={false} zoomControl={false} aria-label={label}>
      <TileLayer url={SATELLITE} maxNativeZoom={17} maxZoom={20} />
      <FitTo geometry={field} pad={compact ? 4 : 24} />
      {neighbours.map((g, i) => (
        <GeoJSON key={`n${i}`} data={g as never} style={{ color: "#e7dfd3", weight: 1, fillOpacity: 0.05 }} />
      ))}
      <GeoJSON key="field" data={field as never} style={{ color: COLORS.field, weight: 3, fillOpacity: 0 }} />
      {healthy.map((c) => (
        <GeoJSON key={c.id} data={c.polygon as never} style={{ color: "#ffffff", weight: 0.5, opacity: 0.35, fillOpacity: 0 }} />
      ))}
      {flagged.map((c) => (
        <GeoJSON key={c.id} data={c.polygon as never} style={{ color: COLORS.flagged, weight: 1, fillColor: COLORS.flagged, fillOpacity: 0.35 }} />
      ))}
      {targets.map((c) => (
        <GeoJSON key={`t-${c.id}-${c.id === activeTarget}-${c.visited}`} data={c.polygon as never}
          style={{ color: c.visited ? "#2f7a40" : COLORS.target, weight: c.id === activeTarget ? 4 : 2,
            fillColor: c.visited ? "#2f7a40" : COLORS.target, fillOpacity: c.id === activeTarget ? 0.55 : 0.3 }} />
      ))}
      {zone && <GeoJSON key={JSON.stringify(zone).length} data={zone as never} style={{ color: COLORS.zone, weight: 3, dashArray: "6 4", fillOpacity: 0.25 }} />}
      {trail.length > 1 && <Polyline positions={trail.map(latlng)} pathOptions={{ color: COLORS.zone, weight: 3 }} />}
      {route && <Polyline positions={route.coordinates.map((p) => latlng(p as [number, number]))} pathOptions={{ color: COLORS.route, weight: 2, dashArray: sprayed ? "4 5" : undefined, opacity: sprayed ? 0.8 : 1 }} />}
      {sprayed && sprayed.length > 1 && <Polyline positions={sprayed.map(latlng)} pathOptions={{ color: COLORS.route, weight: 5 }} />}
      {drone && <CircleMarker center={latlng(drone)} radius={8} pathOptions={{ color: "#111", fillColor: COLORS.route, fillOpacity: 1, weight: 2 }} />}
      {me && <CircleMarker center={latlng(me)} radius={9} pathOptions={{ color: "#fff", fillColor: COLORS.me, fillOpacity: 1, weight: 3 }} />}
    </MapContainer>
  );
}
