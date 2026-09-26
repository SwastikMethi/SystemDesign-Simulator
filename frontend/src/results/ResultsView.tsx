import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play, Save } from 'lucide-react'
import type { Challenge, Case, Design, Metric, Outcome, Results, Run, Snapshot, Trace } from '../api/client'
import { api } from '../api/client'
import { RecordedGraph } from './RecordedGraph'
import { evidenceTarget, outcomeKey } from './evidence'

type Props = { challenge: Challenge; run: Run; results: Results | null; onError: (message: string) => void }
const words = (value: string) => value.replaceAll('_', ' ')
const metricText = (metric: Metric | null | undefined) => metric?.value == null ? `Unavailable${metric?.unavailable_reason ? ` · ${metric.unavailable_reason}` : ''}` : `${Number.isInteger(metric.value) ? metric.value : metric.value.toFixed(2)} ${metric.unit}`

export function ResultsView({ challenge, run, results, onError }: Props) {
  const cases = results?.assessment?.case_results || results?.cases || []
  const [design, setDesign] = useState<Design | null>(null)
  const [caseId, setCaseId] = useState('')
  const [operationId, setOperationId] = useState('all')
  const [selectedOutcomeKey, setSelectedOutcomeKey] = useState<string | null>(null)
  const [traceId, setTraceId] = useState('')
  const [trace, setTrace] = useState<Trace | null>(null)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [timeUs, setTimeUs] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [failureWindow, setFailureWindow] = useState('')
  const selectedCase: Case | undefined = cases.find(c => c.case_id === caseId) || cases[0]
  const selectedOutcome = selectedCase?.requirement_outcomes.find(o => outcomeKey(o) === selectedOutcomeKey)
  const displayedMetrics = Object.entries(selectedCase?.operation_metrics || {}).filter(([operation]) => operationId === 'all' || operation === operationId).flatMap(([operation, values]) => Object.entries(values).map(([name, metric]) => ({ operation, name, metric })))
  const maxTime = Math.max(snapshots.at(-1)?.time_us || 0, trace?.events.at(-1)?.time_us || 0)
  const snapshot = useMemo(() => [...snapshots].reverse().find(item => item.time_us <= timeUs) || snapshots[0], [snapshots, timeUs])
  const markers = useMemo(() => (trace?.events || []).slice(0, 100), [trace])

  useEffect(() => {
    let active = true
    setDesign(null)
    api.revision(run.design_id, run.revision_id).then(value => { if (active) setDesign(value) }).catch(error => { if (active) onError(error.message) })
    return () => { active = false }
  }, [run.design_id, run.revision_id])
  useEffect(() => {
    let active = true
    setSnapshots([]); setTimeUs(0); setPlaying(false); setTraceId(''); setTrace(null); setFailureWindow('')
    if (selectedCase) api.snapshots(run.run_id, selectedCase.case_id).then(page => { if (active) setSnapshots(page.items) }).catch(error => { if (active) onError(error.message) })
    return () => { active = false }
  }, [run.run_id, selectedCase?.case_id])
  useEffect(() => {
    if (!selectedCase || !selectedOutcome) return
    const target = evidenceTarget(selectedCase, selectedOutcome)
    setPlaying(false); setTraceId(target.traceId); setTimeUs(target.timeUs); setFailureWindow(target.description)
  }, [run.run_id, selectedCase?.case_id, selectedOutcomeKey])
  useEffect(() => {
    let active = true
    setTrace(null)
    if (selectedCase && traceId) api.trace(run.run_id, selectedCase.case_id, traceId).then(item => { if (active) { setTrace(item); setTimeUs(item.events[0]?.time_us || 0) } }).catch(error => { if (active) onError(error.message) })
    return () => { active = false }
  }, [run.run_id, selectedCase?.case_id, traceId])
  useEffect(() => {
    if (!playing || !maxTime) return
    let frame = 0, last = 0
    const tick = (now: number) => {
      if (last) setTimeUs(value => { const next = Math.min(maxTime, value + (now-last) * 1000 * speed); if (next >= maxTime) setPlaying(false); return next })
      last = now
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, maxTime, speed])

  const inspect = (outcome: Outcome) => {
    setSelectedOutcomeKey(outcomeKey(outcome))
    if (!selectedCase) return
    const target = evidenceTarget(selectedCase, outcome)
    setPlaying(false); setTraceId(target.traceId); setTimeUs(target.timeUs); setFailureWindow(target.description)
  }
  const firstFailure = () => {
    const failed = cases.flatMap(c => c.requirement_outcomes.filter(o => o.status === 'fail').map(o => ({ case: c, outcome: o }))).at(0)
    if (!failed) return
    setCaseId(failed.case.case_id)
    setSelectedOutcomeKey(outcomeKey(failed.outcome))
    if (failed.case.case_id === selectedCase?.case_id) inspect(failed.outcome)
  }
  const step = (direction: -1 | 1) => {
    setPlaying(false)
    const times = [...new Set([...snapshots, ...(trace?.events || [])].map(item => item.time_us))].sort((a,b) => a-b)
    const target = direction > 0 ? times.find(value => value > timeUs) : times.filter(value => value < timeUs).at(-1)
    if (target !== undefined) setTimeUs(target)
  }
  const saveEvidence = async () => { if (!selectedCase || !snapshot) return; try { await api.saveSnapshot(run.run_id, { title: `${challenge.title} · ${selectedCase.case_id} · ${snapshot.time_us} µs`, case_id: selectedCase.case_id, time_us: snapshot.time_us }) } catch (error) { onError((error as Error).message) } }

  return <div className="results-view">
    <div className="results-heading"><div><h2>{run.mode === 'assessment' ? 'Assessment' : run.mode === 'preview' ? 'Quick preview' : 'Experiment'} <span className={`status ${run.assessment_status}`}>{words(run.assessment_status)}</span></h2><p>{run.mode === 'assessment' ? 'Results from the full scenario and seed suite.' : 'This run cannot mark the challenge complete.'} Frozen revision {run.revision_id.slice(0,12)}.</p></div><button className="secondary" onClick={firstFailure} disabled={!cases.some(c => c.requirement_outcomes.some(o => o.status === 'fail'))}>Jump to first failure</button></div>
    {run.execution_status !== 'completed' && <p className="notice">Run {words(run.execution_status)}. Completed cases remain available below.</p>}
    {!results || !cases.length ? <div className="empty-state"><h3>No results yet</h3><p>Run a preview or full assessment to inspect measured behavior.</p></div> : <>
      <div className="result-filters"><label>Scenario and seed <select value={selectedCase?.case_id || ''} onChange={e => { setCaseId(e.target.value); setSelectedOutcomeKey(null) }}>{cases.map(c => <option key={c.case_id} value={c.case_id}>{c.scenario_id} · seed {c.seed}</option>)}</select></label><label>Operation <select value={operationId} onChange={e => setOperationId(e.target.value)}><option value="all">All operations</option>{challenge.operations.map(o => <option key={o.id} value={o.id}>{o.id}</option>)}</select></label></div>
      <section className="requirement-section"><h3>Requirements</h3><div className="requirement-table" role="table" aria-label="Requirement outcomes"><div className="table-head" role="row"><span>Requirement</span><span>Target</span><span>Observed</span><span>Status</span><span>Evidence</span></div>{challenge.requirements.map(req => { const outcomes = selectedCase?.requirement_outcomes.filter(o => o.requirement_id === req.id) || []; return outcomes.length ? outcomes.map((outcome,i) => <div className={`requirement-row ${selectedOutcomeKey === outcomeKey(outcome) ? 'active' : ''}`} role="row" key={`${req.id}-${i}`}><span><strong>{req.id}</strong> {req.description}{outcome.operation_id && <small>{outcome.operation_id}</small>}</span><span>{req.operator} {req.threshold} {req.unit}</span><span>{metricText(outcome.measured)}</span><span className={`status ${outcome.status}`}>{words(outcome.status)}</span><span><button className="text-button" onClick={() => inspect(outcome)}>Inspect evidence</button></span></div>) : <div className="requirement-row" role="row" key={req.id}><span><strong>{req.id}</strong> {req.description}</span><span>{req.operator} {req.threshold} {req.unit}</span><span>Unavailable</span><span className="status not_evaluated">Not evaluated</span><span>—</span></div> })}</div></section>
      {selectedOutcome && <section className="evidence-section"><h3>Evidence for {selectedOutcome.requirement_id}{selectedOutcome.operation_id ? ` · ${selectedOutcome.operation_id}` : ''}</h3><p>{challenge.requirements.find(r => r.id === selectedOutcome.requirement_id)?.description}</p><div className="evidence-grid">{(selectedOutcome?.evidence_ids || []).map(id => { const evidence = selectedCase?.evidence.find(item => item.evidence_id === id); return <div className="evidence-item" key={id}><strong>{id}</strong><span>{evidence ? `${evidence.value ?? 'Unavailable'} ${evidence.unit} · ${evidence.sample_count} samples` : 'Source artifact'}</span><small>{evidence?.scope || ''}</small></div> })}</div>{failureWindow && <p>{failureWindow}</p>}<p className="muted">An aggregate requirement is supported by its scenario window and measurements; one request alone does not prove the cause.</p></section>}
      <div className="replay-workspace">
      <section className="playback"><div className="panel-heading"><div><h3>Replay</h3><p>{selectedCase?.scenario_id} · seed {selectedCase?.seed} · virtual time {(timeUs/1_000_000).toFixed(2)} s</p></div><button className="secondary" disabled={!snapshot} onClick={saveEvidence}><Save size={15}/> Save moment</button></div>
        <div className="playback-controls"><button aria-label="Previous frame" disabled={!snapshot || timeUs <= 0} onClick={() => step(-1)}><ChevronLeft size={18}/></button><button aria-label={playing ? 'Pause replay' : 'Play replay'} disabled={!maxTime} onClick={() => setPlaying(!playing)}>{playing ? <Pause size={18}/> : <Play size={18}/>}</button><button aria-label="Next frame" disabled={!snapshot || timeUs >= maxTime} onClick={() => step(1)}><ChevronRight size={18}/></button><input aria-label="Replay position" type="range" min="0" max={maxTime} value={timeUs} onChange={e => { setPlaying(false); setTimeUs(Number(e.target.value)) }}/><label>Speed <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>{[.5,1,2,4].map(value => <option key={value} value={value}>{value}×</option>)}</select></label><label className="check"><input type="checkbox" checked={reducedMotion} onChange={e => setReducedMotion(e.target.checked)}/> Reduced motion</label></div>
        <p className="playback-note">1× follows recorded virtual time in real time. Counts come from snapshots; selecting a trace follows its recorded events.</p>
        {design && <RecordedGraph design={design} snapshot={snapshot} trace={trace || undefined} timeUs={timeUs} playing={playing} reducedMotion={reducedMotion}/>}
        {trace && <div className="marker-track"><span>Recorded trace events</span><div>{markers.map((event,i) => <button title={`${words(event.event)} at ${event.time_us} µs`} key={i} className="marker" style={{ left: `${100*event.time_us/Math.max(1,maxTime)}%` }} onClick={() => { setPlaying(false); setTimeUs(event.time_us) }}/>)}</div><small>{trace.events.length > 100 ? 'Sampled traffic · first 100 markers shown' : `${markers.length} recorded markers`}{reducedMotion ? ' · motion disabled' : ''}</small></div>}
      </section>
      <section className="trace-section"><h3>Recorded request path</h3><label>Trace <select value={traceId} onChange={e => setTraceId(e.target.value)}><option value="">Choose recorded trace</option>{selectedCase?.trace_refs.map(ref => <option key={ref} value={ref}>{ref}</option>)}</select></label>{trace && <><p>{trace.operation_id} · request {trace.request_id}</p><ol className="trace-events">{trace.events.map((event,i) => <li key={i}><button className="text-button" onClick={() => { setPlaying(false); setTimeUs(event.time_us) }}><time>{(event.time_us/1000).toFixed(2)} ms</time><strong>{words(event.event)}</strong><span>{event.node_id || event.edge_id || ''}</span></button></li>)}</ol></>}</section>
      </div>
      <details className="metric-section">
        <summary>Operation metrics <span>{displayedMetrics.length} measurements</span></summary>
        {displayedMetrics.length ? <div className="measurement-scroll" role="region" aria-label="Operation measurements" tabIndex={0}><table className="measurement-table" aria-label="Operation measurements">
          <thead><tr><th scope="col">Operation</th><th scope="col">Metric</th><th scope="col">Observed</th><th scope="col">Samples</th></tr></thead>
          <tbody>{displayedMetrics.map(({ operation, name, metric }) => <tr key={`${operation}-${name}`}><th scope="row">{operation}</th><td>{words(name)}</td><td>{metricText(metric)}</td><td>{metric.sample_count}</td></tr>)}</tbody>
        </table></div> : <p className="muted">No operation metrics for this selection.</p>}
        <p className="metric-help">p95: 95% of successful responses were at or below this duration. Check failures alongside this value. Credits use fixed fictional profile rates and omit cloud billing dimensions.</p>
      </details>
    </>}
  </div>
}
