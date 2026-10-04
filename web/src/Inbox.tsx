import { useCallback, useEffect, useMemo, useState } from 'react'
import type { JobsApi } from './api'
import { TAB_LABELS, TABS, countByTab, filterJobs, jobTypes, sortJobs, type Sort, type Tab } from './filters'
import { JobCard } from './JobCard'
import { Profile } from './Profile'
import type { InboxJob, Status } from './types'

interface InboxProps {
  api: JobsApi
  aiEnabled: boolean
  email?: string
  onSignOut?: () => void
  banner?: string
}

export function Inbox({ api, aiEnabled, email, onSignOut, banner }: InboxProps) {
  const [jobs, setJobs] = useState<InboxJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('new')
  const [search, setSearch] = useState('')
  const [jobType, setJobType] = useState('')
  const [matchedOnly, setMatchedOnly] = useState(true)
  const [sort, setSort] = useState<Sort>('newest')
  const [showProfile, setShowProfile] = useState(false)

  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    // `cancelled` stops a slow, older request from overwriting a newer one.
    let cancelled = false
    api.listJobs({ matchedOnly }).then(
      (rows) => {
        if (cancelled) return
        setJobs(rows)
        setError('')
        setLoading(false)
      },
      (e: Error) => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, matchedOnly, reloadCount])

  const reload = () => {
    setLoading(true)
    setReloadCount((n) => n + 1)
  }
  const changeMatchedOnly = (value: boolean) => {
    setLoading(true)
    setMatchedOnly(value)
  }

  // Optimistic update: change the screen right away, undo it if saving fails.
  const updateJob = useCallback(
    async (job: InboxJob, status: Status, notes: string) => {
      const replace = (next: InboxJob) => setJobs((all) => all.map((j) => (j.id === next.id ? next : j)))
      replace({ ...job, status, notes })
      try {
        await api.setStatus(job.id, status, notes)
      } catch (e) {
        replace(job)
        setError(`Couldn't save "${job.title}": ${(e as Error).message}`)
      }
    },
    [api],
  )

  const requestAnalysis = useCallback(
    async (job: InboxJob) => {
      setJobs((all) => all.map((j) => (j.id === job.id ? { ...j, analysis_status: 'pending', analysis_error: null } : j)))
      try {
        await api.requestAnalysis(job.id)
      } catch (e) {
        setJobs((all) => all.map((j) => (j.id === job.id ? job : j)))
        setError(`Couldn't request analysis for "${job.title}": ${(e as Error).message}`)
      }
    },
    [api],
  )

  const counts = useMemo(() => countByTab(jobs), [jobs])
  const visible = useMemo(
    () => sortJobs(filterJobs(jobs, { tab, search, jobType }), sort),
    [jobs, tab, search, jobType, sort],
  )
  const types = useMemo(() => jobTypes(jobs), [jobs])

  if (showProfile) return <Profile api={api} onClose={() => setShowProfile(false)} />

  return (
    <div className="app">
      <header className="topbar">
        <h1>jobwatch</h1>
        <div className="topbar-right">
          {aiEnabled && (
            <button className="ghost" onClick={() => setShowProfile(true)} title="What the AI compares jobs against">
              Profile
            </button>
          )}
          <button className="ghost" onClick={reload} disabled={loading} title="Reload jobs">
            {loading ? 'Loading…' : 'Refresh'}
          </button>
          {onSignOut && (
            <button className="ghost" onClick={onSignOut} title={email}>
              Sign out
            </button>
          )}
        </div>
      </header>

      {banner && <p className="banner">{banner}</p>}

      <nav className="tabs" aria-label="Job status">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? 'tab active' : 'tab'} onClick={() => setTab(t)}>
            {TAB_LABELS[t]} <span className="count">{counts[t]}</span>
          </button>
        ))}
      </nav>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search title, description, tags, pay…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search jobs"
        />
        <select value={jobType} onChange={(e) => setJobType(e.target.value)} aria-label="Job type">
          <option value="">Any type</option>
          {types.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        {aiEnabled && (
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
            <option value="newest">Newest first</option>
            <option value="fit">Best fit first</option>
          </select>
        )}
        <label className="toggle">
          <input type="checkbox" checked={matchedOnly} onChange={(e) => changeMatchedOnly(e.target.checked)} />
          Keyword matches only
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      <main className="list">
        {!loading && visible.length === 0 && (
          <p className="center muted">
            {jobs.length === 0 ? 'No jobs yet. The bot adds them every 15 minutes.' : 'Nothing here with these filters.'}
          </p>
        )}
        {visible.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            aiEnabled={aiEnabled}
            onChange={(status, notes) => void updateJob(job, status, notes)}
            onAnalyze={() => void requestAnalysis(job)}
          />
        ))}
      </main>
    </div>
  )
}
