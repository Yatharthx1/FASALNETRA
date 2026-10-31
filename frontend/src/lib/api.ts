import type { AppEvent, CallResult, Case, DidiProfile, Field, IvrPrompt, Job, Risk, Scan } from "../types/api";

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
  warningCall: (id: number) => post<CallResult>(`/cases/${id}/warning-call`),
  resultCall: (id: number) => post<CallResult>(`/cases/${id}/result-call`),
  keypad: (phone: string, digit: string) => post<IvrPrompt>("/ivr/simulate/registered", { phone, digits: digit }),
  traps: (id: number, counts: number[]) => post<Case>(`/cases/${id}/traps`, { counts }),
  walk: (id: number, trail: [number, number][]) => post<Case>(`/cases/${id}/walk`, { trail }),
  evidence: (id: number) => post<Case>(`/cases/${id}/evidence`),
  uploadPhoto: (id: number, file: Blob, f: { kind: string; spot: number; cell_id?: string; lat?: number; lon?: number }) => {
    const form = new FormData();
    form.append("file", file, "photo.jpg");
    Object.entries(f).forEach(([k, v]) => v !== undefined && form.append(k, String(v)));
    return req<Case["photos"][number]>(`/cases/${id}/photos`, { method: "POST", body: form });
  },

  bookDidi: (id: number) => post<Job>(`/cases/${id}/book-didi`),
  didiProfile: () => req<DidiProfile>("/didi/profile"),
  jobs: () => req<Job[]>("/didi/jobs"),
  jobAction: (id: number, action: string) => post<Job>(`/didi/jobs/${id}`, { action }),
  waypointsUrl: (id: number) => `${BASE}/didi/jobs/${id}/waypoints`,

  events: (caseId?: number) => req<AppEvent[]>(`/events${caseId ? `?case_id=${caseId}` : ""}`),
  reset: () => post<AppEvent>("/demo/reset"),
};

export function eventsSocket(onEvent: (e: AppEvent) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout>;
  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}${BASE}/ws/events`);
    ws.onmessage = (m) => {
      const e = JSON.parse(m.data) as AppEvent;
      if (e.type !== "heartbeat") onEvent(e);
    };
    ws.onclose = () => { if (!closed) retry = setTimeout(open, 2000); };
  };
  open();
  return () => { closed = true; clearTimeout(retry); ws?.close(); };
}
