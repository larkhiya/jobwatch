// Shapes of the data coming from the `inbox` view (see supabase/schema.sql).

export const STATUSES = ['new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'skipped'] as const
export type Status = (typeof STATUSES)[number]

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
}
