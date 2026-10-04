import { describe, expect, it } from 'vitest'
import demoRows from './demo-data.json'
import { countByTab, filterJobs, jobTypes, tabOf, timeAgo } from './filters'
import type { InboxJob } from './types'

const jobs = demoRows as InboxJob[]

describe('tabOf', () => {
  it('groups everything after applying under Applied', () => {
    expect(tabOf('interviewing')).toBe('applied')
    expect(tabOf('offer')).toBe('applied')
    expect(tabOf('rejected')).toBe('applied')
    expect(tabOf('new')).toBe('new')
    expect(tabOf('skipped')).toBe('skipped')
  })
})

describe('filterJobs', () => {
  it('filters by tab', () => {
    const applied = filterJobs(jobs, { tab: 'applied', search: '', jobType: '' })
    expect(applied.map((j) => j.title)).toEqual(['Senior WordPress Developer'])
    expect(filterJobs(jobs, { tab: 'all', search: '', jobType: '' })).toHaveLength(jobs.length)
  })

  it('searches title, snippet, tags and salary, ignoring case', () => {
    const hits = filterJobs(jobs, { tab: 'all', search: 'SHOPIFY', jobType: '' })
    expect(hits.length).toBeGreaterThan(1)
    expect(hits.every((j) => [j.title, j.snippet, ...j.tags].join(' ').toLowerCase().includes('shopify'))).toBe(true)
  })

  it('filters by job type', () => {
    const gigs = filterJobs(jobs, { tab: 'all', search: '', jobType: 'Gig' })
    expect(gigs.length).toBeGreaterThan(0)
    expect(gigs.every((j) => j.job_type === 'Gig')).toBe(true)
  })
})

describe('countByTab', () => {
  it('counts each tab and the total', () => {
    const counts = countByTab(jobs)
    expect(counts.all).toBe(30)
    expect(counts.applied).toBe(1)
    expect(counts.saved).toBe(1)
    expect(counts.skipped).toBe(1)
    expect(counts.new).toBe(27)
  })
})

describe('jobTypes', () => {
  it('lists distinct job types, sorted', () => {
    expect(jobTypes(jobs)).toEqual([...new Set(jobTypes(jobs))].sort())
    expect(jobTypes(jobs)).toContain('Full Time')
  })
})

describe('timeAgo', () => {
  const now = new Date('2026-10-04T12:00:00Z')
  it('formats recent times compactly', () => {
    expect(timeAgo('2026-10-04T11:59:40Z', now)).toBe('just now')
    expect(timeAgo('2026-10-04T11:48:00Z', now)).toBe('12m ago')
    expect(timeAgo('2026-10-04T07:00:00Z', now)).toBe('5h ago')
    expect(timeAgo('2026-10-01T12:00:00Z', now)).toBe('3d ago')
  })
  it('handles missing dates', () => {
    expect(timeAgo(null, now)).toBe('')
  })
})
