// Data access. The UI only talks to this interface, so it runs the same against the real
// Supabase database or the built-in demo data (used when Supabase isn't configured).

import type { SupabaseClient } from '@supabase/supabase-js'
import demoRows from './demo-data.json'
import type { InboxJob, Status } from './types'

export interface JobsApi {
  listJobs(options: { matchedOnly: boolean }): Promise<InboxJob[]>
  setStatus(jobId: string, status: Status, notes: string): Promise<void>
  amIAllowed(): Promise<boolean>
}

const LIST_LIMIT = 500

export function supabaseApi(client: SupabaseClient): JobsApi {
  return {
    async listJobs({ matchedOnly }) {
      let query = client
        .from('inbox')
        .select('*')
        .order('posted_at', { ascending: false, nullsFirst: false })
        .limit(LIST_LIMIT)
      if (matchedOnly) query = query.not('matched_keyword', 'is', null)
      const { data, error } = await query
      if (error) throw error
      return data as InboxJob[]
    },

    async setStatus(jobId, status, notes) {
      const { error } = await client
        .from('job_actions')
        .upsert({ job_id: jobId, status, notes, updated_at: new Date().toISOString() })
      if (error) throw error
    },

    async amIAllowed() {
      const { data, error } = await client.rpc('am_i_allowed')
      if (error) throw error
      return data === true
    },
  }
}

export function demoApi(): JobsApi {
  // A private copy, so changes in the demo only last until the page reloads.
  const rows = (demoRows as InboxJob[]).map((row) => ({ ...row }))
  return {
    async listJobs({ matchedOnly }) {
      return rows.filter((row) => !matchedOnly || row.matched_keyword).map((row) => ({ ...row }))
    },
    async setStatus(jobId, status, notes) {
      const row = rows.find((r) => r.id === jobId)
      if (row) Object.assign(row, { status, notes, status_updated_at: new Date().toISOString() })
    },
    async amIAllowed() {
      return true
    },
  }
}
