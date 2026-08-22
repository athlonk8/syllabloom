export interface Video {
  id: number;
  provider: string;
  external_id: string;
  embed_url: string | null;
  thumbnail_url: string | null;
  is_embeddable: boolean;
}

export interface Lecture {
  id: number;
  module_id: number | null;
  title: string;
  description: string | null;
  order_index: number;
  source_url: string | null;
  duration_seconds: number | null;
  slides_url: string | null;
  notes_url: string | null;
  video: Video | null;
}

export interface Progress {
  lecture_completion: number;
  assignment_completion: number;
  course_completion: number;
  lectures: Array<{
    lecture_id: number;
    video_id?: number;
    fraction: number;
    completed: boolean;
    watched_seconds: number;
    duration_seconds?: number | null;
    resume_position_seconds?: number;
  }>;
  required_lecture_count: number;
  completed_lecture_count: number;
  required_assignment_count: number;
  passed_assignment_count: number;
  average_assignment_score: number | null;
}

export interface Resource {
  id: number;
  title: string;
  resource_url: string;
  source_page_url: string | null;
  resource_type: string;
  detected_as_official: boolean;
  protected_resource: boolean;
  access_status: string;
  local_path: string | null;
  provenance: Record<string, unknown>;
}

export interface Assignment {
  id: number;
  key: string;
  title: string;
  description: string | null;
  official_url: string | null;
  source_page_url: string | null;
  official: boolean;
  protected_resource: boolean;
  requirement_level?: string;
  status: string;
  local_root: string | null;
  rubric_url?: string | null;
  ai_policy?: string | null;
  resources: Resource[];
}

export interface GradeCriterion {
  title: string;
  score: number | null;
  max_score: number | null;
  feedback: string;
}

export interface GradeResult {
  score?: number;
  score_type?: string;
  confidence?: number;
  conceptual_understanding?: number;
  reasoning?: number;
  technical_accuracy?: number;
  clarity?: number;
  strengths?: string[];
  issues?: string[];
  critical_errors?: string[];
  suggested_review_topics?: string[];
  summary?: string;
  detailed_feedback?: string;
  rubric_breakdown?: GradeCriterion[];
  status?: string;
  error?: string;
}

export interface Grade {
  id: number;
  score: number | null;
  score_type: string;
  confidence: number | null;
  status: string;
  result: GradeResult;
  created_at?: string;
}

export interface GradingRun {
  id: number;
  provider: string;
  status: string;
  result: GradeResult;
  stdout: string | null;
  stderr: string | null;
  runtime_seconds?: number | null;
  created_at?: string;
}

export interface Submission {
  id: number;
  version: number;
  status: string;
  submitted_at: string;
  grades: Grade[];
  runs: GradingRun[];
}

export interface AssignmentWorkspace {
  assignment: Assignment;
  answer: string;
  answer_path: string;
  storage: "local" | "obsidian";
  history: Submission[];
  saved_at?: string;
}

export interface Course {
  id: number;
  name: string;
  code: string | null;
  version: string | null;
  year?: string | null;
  quarter?: string | null;
  official_course_url: string | null;
  source_type: string;
  description: string | null;
  channel_name: string | null;
  instructors: string[];
  course_ai_policy?: string | null;
  course_ai_policy_url?: string | null;
  import_status: string;
  progress: Progress;
  modules?: Array<{ id: number; title: string; description: string | null; order_index: number }>;
  lectures?: Lecture[];
  resources?: Resource[];
  assignments?: Assignment[];
  sources?: Array<{ source_url: string; title: string | null; access_status: string; explanation: string | null }>;
}

export interface Dashboard {
  courses: Course[];
  today_learning_seconds: number;
  weekly_learning_seconds: number;
  recent_grades: Array<{ id: number; score: number | null; score_type: string; status: string }>;
  certificates: Array<{ id: number; certificate_id: string; type: string; course_id: number }>;
  streak_days: number;
}

export interface BilibiliSession {
  logged_in: boolean;
  mid: number | null;
  uname: string | null;
  vip_status: number | null;
}

export interface BilibiliQuality {
  id: number;
  label: string;
}

export interface BilibiliPlayback {
  bvid: string;
  cid: number;
  page: number;
  pages_total: number;
  title: string;
  part: string;
  duration_seconds: number | null;
  timelength_ms: number | null;
  quality_id: number;
  qualities: BilibiliQuality[];
  logged_in: boolean;
  stream_url: string;
}

export interface BilibiliQrCode {
  qrcode_key: string;
  qr_svg: string;
}

export interface BilibiliQrPollResult {
  status: "waiting" | "scanned" | "confirmed" | "expired" | "unknown";
  session?: BilibiliSession;
}
