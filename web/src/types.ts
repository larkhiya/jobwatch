// Shapes of the data coming from the `inbox` view (see supabase/schema.sql).

export const STATUSES = ['new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'skipped'] as const
export type Status = (typeof STATUSES)[number]

export type Verdict = 'apply' | 'maybe' | 'skip'

/** Claude's full analysis, written by the bot after you tap "Analyze". */
export interface AiDetails {
  score: number
  verdict: Verdict
  summary: string
  strengths: string[]
  gaps: string[]
  red_flags: string[]
  how_to_improve: string[]
  application_message: string
}

export interface InboxJob {
  id: string
  title: string
  url: string
  posted_at: string | null
  salary: string | null
  job_type: string | null
  snippet: string
  tags: string[]
  matched_keyword: string | null
  first_seen_at: string
  updated_at: string
  status: Status
  notes: string
  status_updated_at: string | null
  // Optional AI (null until scored / analyzed)
  ai_score: number | null
  ai_verdict: Verdict | null
  ai_summary: string | null
  ai_details: AiDetails | null
  analysis_status: 'pending' | 'done' | 'failed' | null
  analysis_error: string | null
}
