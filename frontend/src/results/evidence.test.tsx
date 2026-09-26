import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { SuggestedExperiment } from './ExperimentView'
import type { Case, Outcome } from '../api/client'
import { evidenceTarget, outcomeKey } from './evidence'

describe('result identity and coach experiments', () => {
  it('keeps evidence for the same requirement on different operations separate', () => {
    expect(outcomeKey({ requirement_id: 'R01', operation_id: 'read' })).not.toBe(outcomeKey({ requirement_id: 'R01', operation_id: 'write' }))
  })

  it('renders a completed review experiment with its string tradeoff', () => {
    const html = renderToStaticMarkup(<SuggestedExperiment proposal={{ purpose: 'Move reads through cache', expected_tradeoffs: 'Lower read latency with higher memory cost', patch: { nodes: [] } }} index={0} busy={false} onTest={() => {}}/>)
    expect(html).toContain('Lower read latency with higher memory cost')
    expect(html).toContain('Test proposal')
  })

  it.each(['successful stale read', 'delivered duplicate effect', 'late delivered job'])('opens saved first-violation evidence for a %s', () => {
    const outcome = { requirement_id: 'R03', evidence_ids: ['metric', 'metric:first'] } as Outcome
    const recordedCase = { case_id: 'burst-101', trace_refs: ['trace:warmup-error', 'trace:violation'], evidence: [
      { evidence_id: 'metric', artifact_ref: 'case:burst-101:window:60000000:360000000' },
      { evidence_id: 'metric:first', type: 'first_violation', value: 'violation', artifact_ref: 'trace:violation' },
    ] } as Case
    expect(evidenceTarget(recordedCase, outcome).traceId).toBe('trace:violation')
    expect(evidenceTarget(recordedCase, outcome).description).toContain('request violation')
  })

  it('opens the recorded aggregate latency window without selecting an unrelated failed request', () => {
    const outcome = { evidence_ids: ['latency'] } as Outcome
    const recordedCase = { case_id: 'burst-202', trace_refs: ['trace:warmup-error'], evidence: [
      { evidence_id: 'latency', type: 'response_p95_ms', artifact_ref: 'case:burst-202:window:60000000:360000000' },
    ] } as Case
    expect(evidenceTarget(recordedCase, outcome)).toEqual({ traceId: '', timeUs: 60000000, description: 'Recorded calculation window: 60–360 s. Inspect this interval and its aggregate measurements.' })
  })
})
