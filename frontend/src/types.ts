export type Severity = "critical" | "warning" | "info";
export type Category = "server" | "network" | "database" | "application";
export interface Recommendation {
  id: string;
  title: string;
  condition: string;
  steps: string[];
  cautions: string;
  category: Category;
  source: string;
  similarity: number;
  revision: number;
  excerpt: string;
}
export interface Incident {
  id: string;
  title: string;
  description: string;
  host: string;
  source: string;
  severity: Severity;
  category: Category;
  priority: string;
  confidence: number;
  needs_review: boolean;
  rationale: string;
  lifecycle: string;
  handling: string;
  first_seen: string;
  last_seen: string;
  recommendations: Recommendation[];
  recommendation_status: string;
  labels: Record<string, string>;
}
export interface Runbook {
  id: string;
  title: string;
  condition: string;
  steps: string[];
  cautions: string;
  category: Category;
  source: string;
  status?: string;
  error?: string;
  similarity?: number;
  revision?: number;
}
export interface Job {
  id: string;
  filename: string;
  status: string;
  progress: number;
  total: number;
  error: string;
}
export interface Source {
  source: string;
  state: null | {
    last_success: string | null;
    last_attempt: string | null;
    error: string;
    count: number;
  };
  demo_mode: boolean;
  interval_seconds: number;
}
export interface Audit {
  id: string;
  actor: string;
  action: string;
  comment: string;
  created_at: string;
  incident_id: string | null;
}
export interface Summary {
  critical: number;
  warning: number;
  info: number;
  pending: number;
  runbooks: number;
}
