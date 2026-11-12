export type Severity = "critical" | "warning" | "info";
export type Category = "server" | "network" | "database" | "application";
export interface Feedback {
  helpful: boolean;
  actor: string;
  operator_id: string;
  updated_at: string;
}
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
  matched_terms?: string[];
  explanation?: string;
  feedback?: Feedback | null;
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
  confidence: number | null;
  classification_correction?: {
    actor: string;
    operator_id: string;
    updated_at: string;
    comment: string;
  } | null;
  automatic_classification?: {
    severity: Severity;
    category: Category;
    priority: string;
    confidence: number;
    rationale: string;
  };
  recommendation_generation: number;
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
  helpful_count: number;
  not_helpful_count: number;
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
  status: "waiting" | "online" | "stale" | "error";
  stale_after_seconds: number;
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
  details?: {
    before: unknown;
    after: unknown;
    runbook_id?: string;
    revision?: number;
  } | null;
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
