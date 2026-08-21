export type RiskTier = "critical" | "elevated" | "low";

export type Stats = {
  objects_tracked: number;
  events_screened: number;
  critical_count: number;
  elevated_count: number;
  low_count: number;
  last_screened_at: string | null;
  last_refresh_at: string | null;
  last_refresh_display: string | null;
  data_source: string;
  refresh_in_progress: boolean;
  last_refresh_error: string | null;
};

export type EventObject = {
  norad_id: number;
  name: string;
  object_type: string;
  type_description: string;
};

export type Factor = { raw_value: number; contribution: number; weight: number; caption: string };
export type EventSummary = {
  id: string;
  object_a: EventObject;
  object_b: EventObject;
  tca: string;
  tca_display: string;
  miss_distance_km: number;
  miss_distance_display: string;
  relative_velocity_kmps: number;
  relative_velocity_display: string;
  risk_score: number;
  risk_tier: RiskTier;
  summary: string;
  factor_breakdown: Record<string, Factor>;
  screened_at: string;
};
export type EventDetail = EventSummary & {
  trend_history: { screened_at: string; risk_score: number; miss_distance_km: number }[];
  trend_label: string;
  dominant_factor: string;
};
export type AgentText = { source: "ollama" | "template"; model: string; provider_error?: string | null };
export type Explain = AgentText & { headline: string; explanation: string; operator_focus: string[]; caveat: string };
export type Recommendation = AgentText & { recommendation: string; screened_at: string };
export type QueryResult = AgentText & { answer: string; referenced_event_ids: string[] };
export type Insights = AgentText & { insights: { observation: string; related_event_ids: string[] }[] };

export type ObjectListItem = {
  norad_id: number;
  name: string;
  object_type: string;
  type_description: string;
  epoch: string | null;
};
export type ObjectList = { items: ObjectListItem[]; total_returned: number };
export type PropagatedObject = EventObject & {
  epoch: string;
  last_updated: string;
  latitude_deg?: number | null;
  longitude_deg?: number | null;
  altitude_km?: number | null;
  altitude_display?: string | null;
};
export type ScreeningConfig = {
  horizon_hours: number;
  conjunction_threshold_km: number;
  coorbital_relative_velocity_kmps: number;
  object_limit: number;
  refresh_interval_hours: number;
};
export type RiskConfig = {
  weights: Record<string, number>;
  critical_threshold: number;
  elevated_threshold: number;
};
export type Config = { screening: ScreeningConfig; risk: RiskConfig };

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { "content-type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  events: (limit = 25) => request<{ items: EventSummary[]; total_returned: number }>(`/api/events?limit=${limit}`),
  event: (id: string) => request<EventDetail>(`/api/events/${id}`),
  explain: (id: string) => request<Explain>(`/api/events/${id}/explain`, { method: "POST" }),
  recommendation: (id: string) => request<Recommendation>(`/api/events/${id}/recommendation`),
  query: (question: string) => request<QueryResult>("/api/agent/query", { method: "POST", body: JSON.stringify({ question }) }),
  insights: () => request<Insights>("/api/agent/insights"),
  refresh: () => request<{ job_id: string; status: string; message: string }>("/api/refresh", { method: "POST" }),
  objects: (search = "", limit = 200) =>
    request<ObjectList>(`/api/objects?limit=${limit}${search ? `&search=${encodeURIComponent(search)}` : ""}`),
  object: (noradId: number) => request<PropagatedObject>(`/api/objects/${noradId}`),
  config: () => request<Config>("/api/config"),
};

export function websocketUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/events";
  return url.toString();
}
