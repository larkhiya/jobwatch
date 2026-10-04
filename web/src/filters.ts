// Pure helpers for the inbox: which tab a job belongs to, filtering, counts, and times.
// No React here, so they're easy to unit test (see filters.test.ts).

import type { InboxJob, Status } from './types'

export const TABS = ['new', 'saved', 'applied', 'skipped', 'all'] as const
export type Tab = (typeof TABS)[number]

export const TAB_LABELS: Record<Tab, string> = {
  new: 'New',
  saved: 'Saved',
  applied: 'Applied',
  skipped: 'Skipped',
  all: 'All',
}

/** "Applied" is the whole pipeline after you apply: interviewing, offer and rejected live there too. */
export function tabOf(status: Status): Exclude<Tab, 'all'> {
  switch (status) {
    case 'new':
    case 'saved':
    case 'skipped':
      return status
    default:
      return 'applied'
  }
}

export interface Filters {
  tab: Tab
  search: string
  jobType: string // '' = any
}

export function filterJobs(jobs: InboxJob[], { tab, search, jobType }: Filters): InboxJob[] {
  const needle = search.trim().toLowerCase()
  return jobs.filter((job) => {
    if (tab !== 'all' && tabOf(job.status) !== tab) return false
    if (jobType && job.job_type !== jobType) return false
    if (!needle) return true
    const haystack = [job.title, job.snippet, job.salary ?? '', ...job.tags].join(' ').toLowerCase()
    return haystack.includes(needle)
  })
}

export function countByTab(jobs: InboxJob[]): Record<Tab, number> {
  const counts: Record<Tab, number> = { new: 0, saved: 0, applied: 0, skipped: 0, all: jobs.length }
  for (const job of jobs) counts[tabOf(job.status)] += 1
  return counts
}

export function jobTypes(jobs: InboxJob[]): string[] {
  return [...new Set(jobs.map((job) => job.job_type).filter((t): t is string => Boolean(t)))].sort()
}

/** "just now", "12m ago", "5h ago", "3d ago", or a date for anything older than a month. */
export function timeAgo(iso: string | null, now: Date = new Date()): string {
  if (!iso) return ''
  const then = new Date(iso)
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days <= 30) return `${days}d ago`
  return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}
