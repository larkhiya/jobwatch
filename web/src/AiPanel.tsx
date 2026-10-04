import { useState } from 'react'
import { fitBand } from './filters'
import type { InboxJob } from './types'

/** Fit badge for the card header, e.g. "Fit 82 · apply". */
export function FitBadge({ job }: { job: InboxJob }) {
  if (job.ai_score === null) return null
  return (
    <span className={`chip fit ${fitBand(job.ai_score)}`} title="Claude's fit score for your profile">
      Fit {job.ai_score}
      {job.ai_verdict ? ` · ${job.ai_verdict}` : ''}
    </span>
  )
}

/** The AI part of a job card: one-line summary, "Analyze", and the full analysis when ready. */
export function AiPanel({ job, onAnalyze }: { job: InboxJob; onAnalyze: () => void }) {
  const [open, setOpen] = useState(false)
  const details = job.ai_details
  const pending = job.analysis_status === 'pending'

  return (
    <div className="ai">
      {job.ai_summary && <p className="ai-summary">{job.ai_summary}</p>}

      <div className="actions">
        {details ? (
          <button className="action" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? 'Hide analysis' : 'Show analysis'}
          </button>
        ) : pending ? (
          <span className="muted small">Analyzing… ready within ~15 minutes, and you'll get an alert.</span>
        ) : (
          <button className="action" onClick={onAnalyze}>
            {job.analysis_status === 'failed' ? 'Try analysis again' : 'Analyze with AI'}
          </button>
        )}
        {details && !pending && (
          <button className="action ghost" onClick={onAnalyze} title="Run the analysis again">
            Re-analyze
          </button>
        )}
      </div>

      {job.analysis_status === 'failed' && job.analysis_error && (
        <p className="error small">Last analysis failed: {job.analysis_error}</p>
      )}

      {details && open && <AnalysisDetails details={details} />}
    </div>
  )
}

function AnalysisDetails({ details }: { details: NonNullable<InboxJob['ai_details']> }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(details.application_message)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="analysis">
      <p>
        <strong>
          Fit {details.score}/100 · {details.verdict}
        </strong>
        : {details.summary}
      </p>
      <Section title="Strengths" items={details.strengths} />
      <Section title="Gaps" items={details.gaps} />
      <Section title="Red flags" items={details.red_flags} empty="None spotted." />
      <Section title="How to become a stronger candidate" items={details.how_to_improve} />
      <h3>Draft application</h3>
      <p className="draft">{details.application_message}</p>
      <button className="action" onClick={() => void copy()}>
        {copied ? 'Copied!' : 'Copy draft'}
      </button>
      <p className="muted small">Edit it before sending: make it yours, and check every claim is true.</p>
    </div>
  )
}

function Section({ title, items, empty }: { title: string; items: string[]; empty?: string }) {
  if (items.length === 0 && !empty) return null
  return (
    <>
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="muted small">{empty}</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </>
  )
}
