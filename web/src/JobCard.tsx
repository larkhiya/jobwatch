import { useState } from 'react'
import { timeAgo } from './filters'
import { STATUSES, type InboxJob, type Status } from './types'

const QUICK_ACTIONS: { status: Status; label: string }[] = [
  { status: 'saved', label: 'Save' },
  { status: 'applied', label: 'Applied' },
  { status: 'skipped', label: 'Skip' },
]

const STATUS_LABELS: Record<Status, string> = {
  new: 'New',
  saved: 'Saved',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
  skipped: 'Skipped',
}

interface JobCardProps {
  job: InboxJob
  onChange: (status: Status, notes: string) => void
}

export function JobCard({ job, onChange }: JobCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [notesOpen, setNotesOpen] = useState(Boolean(job.notes))
  const [notes, setNotes] = useState(job.notes)

  // Tapping the active quick action again undoes it (back to New).
  const toggle = (status: Status) => onChange(job.status === status ? 'new' : status, job.notes)
  const saveNotes = () => {
    if (notes !== job.notes) onChange(job.status, notes)
  }

  return (
    <article className={`card status-${job.status}`}>
      <h2>
        <a href={job.url} target="_blank" rel="noopener noreferrer">
          {job.title}
        </a>
      </h2>

      <p className="meta">
        {job.job_type && <span className="chip">{job.job_type}</span>}
        {job.salary && <span className="chip pay">{job.salary}</span>}
        {job.posted_at && <span title={new Date(job.posted_at).toLocaleString()}>{timeAgo(job.posted_at)}</span>}
        {job.matched_keyword && <span className="chip keyword">matched: {job.matched_keyword}</span>}
      </p>

      {job.snippet && (
        <p className={expanded ? 'snippet' : 'snippet clamp'} onClick={() => setExpanded(!expanded)}>
          {job.snippet}
        </p>
      )}

      {job.tags.length > 0 && <p className="tags">{job.tags.join(' · ')}</p>}

      <div className="actions">
        {QUICK_ACTIONS.map(({ status, label }) => (
          <button
            key={status}
            className={job.status === status ? 'action on' : 'action'}
            aria-pressed={job.status === status}
            onClick={() => toggle(status)}
          >
            {label}
          </button>
        ))}
        <select
          value={job.status}
          onChange={(e) => onChange(e.target.value as Status, job.notes)}
          aria-label="Status"
          className="status-select"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <button className="action ghost" onClick={() => setNotesOpen(!notesOpen)} aria-expanded={notesOpen}>
          Notes{job.notes ? ' •' : ''}
        </button>
      </div>

      {notesOpen && (
        <textarea
          className="notes"
          placeholder="Notes: who you contacted, what you sent, follow-up dates…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={saveNotes}
          rows={3}
        />
      )}
    </article>
  )
}
