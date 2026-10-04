// Data access. The UI only talks to this interface, so it runs the same against the real
// Supabase database or the built-in demo data (used when Supabase isn't configured).

import type { SupabaseClient } from '@supabase/supabase-js'
import demoRows from './demo-data.json'
import type { InboxJob, Status } from './types'

export interface JobsApi {
  listJobs(options: { matchedOnly: boolean }): Promise<InboxJob[]>
  setStatus(jobId: string, status: Status, notes: string): Promise<void>
  amIAllowed(): Promise<boolean>
  // Optional AI
  requestAnalysis(jobId: string): Promise<void>
  getProfile(): Promise<string>
  saveProfile(content: string): Promise<void>
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

    async requestAnalysis(jobId) {
      // Queued; the bot's next run (within ~15 minutes) picks it up and sends an alert when done.
      const { error } = await client.from('analysis_requests').upsert({
        job_id: jobId,
        status: 'pending',
        error: null,
        requested_at: new Date().toISOString(),
        completed_at: null,
      })
      if (error) throw error
    },

    async getProfile() {
      const { data, error } = await client.from('profile').select('content').eq('id', 1).maybeSingle()
      if (error) throw error
      return data?.content ?? ''
    },

    async saveProfile(content) {
      const { error } = await client
        .from('profile')
        .upsert({ id: 1, content, updated_at: new Date().toISOString() })
      if (error) throw error
    },
  }
}

export function demoApi(): JobsApi {
  // A private copy, so changes in the demo only last until the page reloads.
  const rows = (demoRows as InboxJob[]).map((row) => ({ ...row }))
  let profile = ''
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
    async requestAnalysis(jobId) {
      const row = rows.find((r) => r.id === jobId)
      if (row) Object.assign(row, { analysis_status: 'pending', analysis_error: null })
    },
    async getProfile() {
      return profile
    },
    async saveProfile(content) {
      profile = content
    },
  }
}
