import type { Case, Outcome } from '../api/client'

export const outcomeKey = (outcome: Pick<Outcome, 'requirement_id' | 'operation_id'>) => `${outcome.requirement_id}/${outcome.operation_id || ''}`

export function evidenceTarget(recordedCase: Case, outcome: Outcome) {
  const evidence = outcome.evidence_ids.flatMap(id => recordedCase.evidence.filter(item => item.evidence_id === id))
  const violation = evidence.find(item => item.type === 'first_violation' && item.artifact_ref && recordedCase.trace_refs.includes(item.artifact_ref))
  const window = evidence.map(item => /^case:(.+):window:(\d+):(\d+)$/.exec(item.artifact_ref || '')).find(match => match?.[1] === recordedCase.case_id)
  return {
    traceId: violation?.artifact_ref || '',
    timeUs: window ? Number(window[2]) : 0,
    description: violation ? `Recorded first violation · request ${violation.value}.` : window ? `Recorded calculation window: ${Number(window[2])/1_000_000}–${Number(window[3])/1_000_000} s. Inspect this interval and its aggregate measurements.` : 'No navigable trace or calculation window was recorded for this evidence.',
  }
}
