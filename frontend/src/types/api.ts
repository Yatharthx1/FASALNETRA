// Mirrors backend/app/schemas. Keep in sync when a response model changes.
import type { Geometry, LineString, Polygon } from "geojson";

export type Band = "safe" | "watch" | "high";
export type Cause = "yellow_mosaic" | "fungal" | "chewing_damage" | "girdle_beetle" | "water_stress" | "nutrient";

export interface Driver { en: string; hi: string }
export interface CauseRisk { score: number; band: Band; drivers: Driver[] }
export interface RiskDay { date: string; das: number; top: Cause; score: number; band: Band; causes: Record<string, CauseRisk> }
export interface Risk { field_id: string; mode: "replay" | "forecast"; rule_status: string; days: RiskDay[] }

export interface Field {
  id: string; khasra: string; crop: string; sowing_date: string; area_acres: number;
  geometry: Polygon; centroid_lat: number; centroid_lon: number;
  farmer: { id: number; name: string; village: string; language: string };
}

export interface GridCell {
  id: string; polygon: Polygon; centre: [number, number]; ndvi: number | null;
  z_ndvi: number | null; z_ndre: number | null; low_spot: boolean; flagged: boolean;
}
export interface Scan {
  field_id: string; scene_date: string; cells: GridCell[];
  summary: { cells_in_field: number; cells_flagged: number; flagged_acres: number; pattern: string; strength: number };
}

/** reason: why the walk stops here (satellite patch, its far edge, a low spot, the grassy border, or the weakest cell). */
export interface TargetCell {
  id: string; centre: [number, number]; polygon: Polygon; visited: boolean;
  reason?: "satellite_patch" | "patch_edge" | "low_spot" | "border" | "weakest"; patch_acres?: number;
}

export interface Vision {
  label: string; confidence: number; severity: number; whitefly_visible: boolean; symptoms_seen: string;
  quality: { ok: boolean; retake_reason: "blurry" | "dark" | null };
  /** What the farmer would use for this photo's cause, from the ICAR-NSRI table (zone dose comes with the evidence). */
  advice?: { cause: Cause; name_hi: string; name_en: string; product: string | null; dose_per_acre: number | null;
    unit: string | null; pesticide: boolean } | null;
}
/** One phone position sample (5 a second: real GPS fixes and the fused track between them). */
export interface TrackPoint {
  t: number; lat: number; lon: number; accuracy: number; heading: number | null; speed: number | null;
  source: "gps" | "steps" | "hold";
}
export interface Located {
  status: "on_field" | "near_field" | "away"; distance_m: number; accuracy_m: number;
  parcel: { khasra: string | null; village_id: string | null; area_ha: number | null; recorded_crop: string | null } | null;
  parcel_is_mapped_field: boolean;
}

export interface Photo { id: number; kind: string; spot: number; cell_id: string | null; vision: Vision }

export interface Signal { name: string; weight: number; supports: string | null; strength: number; share: number }
export interface SprayPlan {
  product: string; quantity: number; unit: string; dose_per_acre: number; method: string; water_l: number;
  knapsack_tanks: number | null; alternatives: string[];
}
export interface Evidence {
  cause: Cause; name_hi: string; confidence: number; level: "high" | "medium" | "low";
  action: "advise_spray" | "didi_verify" | "advise_no_pesticide" | "expert_check";
  spray_allowed: boolean; agreeing_signals: string[]; low_spot_warning: boolean; signals: Signal[];
  alternatives: { cause: string; share: number }[];
  plan: { cause: Cause; name_hi: string; source: string; cultural: string[]; spray: SprayPlan | null; zone_acres: number } | null;
  savings: { acres_not_sprayed: number; chemical_saved: number; unit: string | null; rupees_saved: number | null };
  /** advisory: high confidence on a crop with a knowledge pack; drone_didi / expert: she or KVK checks first */
  route?: "advisory" | "drone_didi" | "expert"; route_reason?: string;
  advisory?: { say_hi: string; advisory_hi: string; advisory_en: string; source: "llm" | "template"; model?: string; note?: string };
}

export interface Case {
  id: number; field_id: string; status: string; created_at: string; target_cells: TargetCell[];
  keypad: Record<string, boolean>; trap_counts: number[]; walk_trail: [number, number][];
  zone: Geometry | null; zone_acres: number | null; evidence: Evidence | null; photos: Photo[];
}

/** One prompt of the IVR's registered-farmer flows (warning, result, followup), as the web keypad sees it. */
export interface IvrPrompt { phone: string; flow: string; current_step: string; prompt_id: string; prompt_text: string; valid_digits: string[]; is_completed: boolean; message: string }
export interface CallResult { case_id: number; simulated: boolean; call_sid: string | null; first_prompt: IvrPrompt }

export interface Job {
  id: number; case_id: number; status: "new" | "accepted" | "flying" | "done" | "declined"; mode: "spray" | "verify_then_spray";
  plan: NonNullable<Evidence["plan"]>;
  route: { path: LineString | null; waypoints: [number, number][]; passes: number; length_m: number; minutes: number; takeoff: [number, number]; zone: Geometry };
  window: { date: string; best: string | null; slots: { time: string; rain_mm: number; wind_kmh: number | null; ok: boolean }[]; verified?: boolean };
  schedule: { date: string; time: string; kind: "spray" | "verify_then_spray" | "check" | "repeat_spray"; note_hi: string; note_en: string }[];
  savings: {
    pesticide: { saved: number; used: number; unit: string | null }; water_l: { saved: number; used: number };
    flight_min: { saved: number; used: number }; battery: { saved: number; used: number }; fuel_l: { saved: number; used: number; note: string };
    acres_not_sprayed: number; full_field_minutes: number;
  };
  ticket: {
    farmer: string; village: string; khasra: string; crop_days: number; field: Polygon; field_acres: number;
    cause: Cause; confidence: number; level: "high" | "medium" | "low" | null; symptoms: string[]; distance_km: number;
  };
  created_at: string; updated_at: string;
}

export interface DidiProfile {
  name: string; shg: string; village: string; drone: string; batteries_ready: number; tank_l: number; base: [number, number];
  jobs_open: number; jobs_done: number; acres_sprayed: number; acres_saved: number; pesticide_saved: number; pesticide_unit: string;
}

export interface CombinedAdvisory {
  field_id: string;
  score: number;
  band: "safe" | "watch" | "high" | "critical";
  level: "low" | "medium" | "high";
  primary_cause: string;
  primary_cause_en: string;
  primary_cause_hi: string;
  crop_age_das: number;
  synergy_multiplier: number;
  action: {
    code: string;
    en: string;
    hi: string;
    spray_recommended: boolean;
    zone_acres: number | null;
  };
  narrative: {
    en: string;
    hi: string;
  };
  components: {
    satellite: {
      score: number;
      pattern: string;
      strength: number;
      flagged_cells: number;
      flagged_acres: number;
      z_ndre: number | null;
      z_ndvi: number | null;
      low_spot_overlap: number;
      drivers: Driver[];
    };
    weather: {
      score: number;
      vector_dispersal_factor: number;
      fungal_conduciveness_factor: number;
      spray_feasibility?: {
        date: string;
        overall_suitability: string;
        best_window: string | null;
        mean_wind_kmh: number;
        advisory_hi: string;
        advisory_en: string;
      };
      drivers: Driver[];
    };
    crop_stage: {
      das: number;
      vulnerability_factor: number;
    };
  };
  causes: Record<string, {
    score: number;
    sat_component: number;
    wea_component: number;
    crop_component: number;
    synergy_multiplier: number;
  }>;
}

export interface AppEvent { id?: number; ts?: string; type: string; case_id: number | null; payload: Record<string, unknown> }
