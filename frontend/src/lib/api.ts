import type { AppEvent, CallResult, Case, DidiProfile, Field, IvrPrompt, Job, Located, Risk, Scan, TrackPoint } from "../types/api";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : res.statusText);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  field: (id = "demo") => req<Field>(`/fields/${id}`),
  risk: (id = "demo") => req<Risk>(`/fields/${id}/risk`),
  scan: (id = "demo") => req<Scan>(`/fields/${id}/scan`),
  demoWalk: (id = "demo") => req<[number, number][]>(`/fields/${id}/demo-walk`),

  createCase: (field_id = "demo") => post<Case>("/cases", { field_id }),
  getCase: (id: number) => req<Case>(`/cases/${id}`),
  caseByToken: (t: string) => req<Case>(`/cases/by-token?t=${encodeURIComponent(t)}`),
  opened: (id: number) => fetch(`${BASE}/cases/${id}/opened`, { method: "POST" }).then(() => undefined),
  missedCall: (fieldId = "demo") => post<{ phone: string; callback_in_s: number }>(`/fields/${fieldId}/missed-call`),
  ivrPrompt: (phone: string) => post<IvrPrompt>("/ivr/simulate/registered", { phone }),
  warningCall: (id: number) => post<CallResult>(`/cases/${id}/warning-call`),
  resultCall: (id: number) => post<CallResult>(`/cases/${id}/result-call`),
  followupCall: (id: number) => post<CallResult>(`/cases/${id}/followup-call`),
  keypad: (phone: string, digit: string) => post<IvrPrompt>("/ivr/simulate/registered", { phone, digits: digit }),
  traps: (id: number, counts: number[]) => post<Case>(`/cases/${id}/traps`, { counts }),
  walk: (id: number, trail: [number, number][]) => post<Case>(`/cases/${id}/walk`, { trail }),
  track: (id: number, points: TrackPoint[]) => post<{ stored: number; total: number }>(`/cases/${id}/track`, { points }),
  locate: (id: number, at: { lat: number; lon: number; accuracy: number }) => post<Located>(`/cases/${id}/locate`, at),
  evidence: (id: number) => post<Case>(`/cases/${id}/evidence`),
  uploadPhoto: async (id: number, file: Blob, f: { kind: string; spot: number; cell_id?: string; lat?: number; lon?: number }) => {
    const form = new FormData();
    form.append("file", file, "photo.jpg");
    Object.entries(f).forEach(([k, v]) => v !== undefined && form.append(k, String(v)));
    // village 2G/3G drops requests: one quiet retry on a network error (not on a server answer)
    for (let attempt = 0; ; attempt++) {
      try {
        return await req<Case["photos"][number]>(`/cases/${id}/photos`, { method: "POST", body: form });
      } catch (e) {
        if (e instanceof ApiError || attempt >= 1) throw e;
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
  },

  bookDidi: (id: number) => post<Job>(`/cases/${id}/book-didi`),
  didiProfile: () => req<DidiProfile>("/didi/profile"),
  jobs: () => req<Job[]>("/didi/jobs"),
  jobAction: (id: number, action: string) => post<Job>(`/didi/jobs/${id}`, { action }),
  waypointsUrl: (id: number) => `${BASE}/didi/jobs/${id}/waypoints`,

  events: (caseId?: number) => req<AppEvent[]>(`/events${caseId ? `?case_id=${caseId}` : ""}`),
  reset: () => post<AppEvent>("/demo/reset"),
};

const POLL_MS = 2000;

/** Live event feed by polling (works through Vercel's rewrite to the API, which cannot carry WebSockets). */
export function eventsSocket(onEvent: (e: AppEvent) => void): () => void {
  let closed = false;
  let last: number | null = null;   // newest event id seen; null until the first poll sets the baseline
  let timer: ReturnType<typeof setTimeout>;
  const poll = async () => {
    try {
      if (last === null) {
        const latest = await req<AppEvent[]>("/events?limit=1");
        last = latest[0]?.id ?? 0;
      } else {
        const fresh = await req<AppEvent[]>(`/events?after=${last}`);
        for (const e of fresh) { last = Math.max(last, e.id ?? last); if (!closed) onEvent(e); }
      }
    } catch { /* offline or API restarting: try again next tick */ }
    if (!closed) timer = setTimeout(poll, POLL_MS);
  };
  poll();
  return () => { closed = true; clearTimeout(timer); };
}
