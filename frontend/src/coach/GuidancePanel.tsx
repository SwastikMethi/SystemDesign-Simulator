import { useEffect, useRef, useState } from 'react'
import type { Design, Guidance } from '../api/client'
import { api } from '../api/client'
import { Dialog } from '../Dialog'

type Props = { aiConfigured: boolean; onClose: () => void; onViewReference: () => void; saveDesign: () => Promise<Design | null> }

export function GuidancePanel({ aiConfigured, onClose, onViewReference, saveDesign }: Props) {
  const [mode, setMode] = useState<Guidance['mode']>('hint')
  const [focus, setFocus] = useState('')
  const [guidance, setGuidance] = useState<Guidance | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sourceHint, setSourceHint] = useState<Guidance | null>(null)
  const requestEpoch = useRef(0)
  const pending = busy || guidance?.status === 'queued'

  useEffect(() => () => { requestEpoch.current += 1 }, [])

  useEffect(() => {
    if (!guidance || guidance.status !== 'queued') return
    let active = true
    const timer = window.setInterval(() => api.guidance(guidance.design_id, guidance.guidance_id).then(value => { if (active) { setGuidance(value); setError('') } }).catch(err => { if (active) setError((err as Error).message) }), 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [guidance?.design_id, guidance?.guidance_id, guidance?.status])

  const ask = async (requestedMode = mode, evidenceStep = false, hint = sourceHint) => {
    if (pending) return
    const epoch = ++requestEpoch.current
    const source = requestedMode === 'answer' ? hint : null
    const requestedFocus = source ? source.focus : evidenceStep ? guidance?.focus : focus.trim()
    setMode(requestedMode); setSourceHint(source); setBusy(true); setError(''); setGuidance(null)
    if (source) setFocus(source.focus || '')
    try {
      const revision = await saveDesign()
      if (epoch !== requestEpoch.current) return
      if (!revision) { setError('Save the draft before requesting guidance.'); return }
      const accepted = await api.startGuidance(revision.design_id, { revision_id: revision.revision_id, mode: requestedMode, focus: requestedFocus || null, source_guidance_id: source?.guidance_id || null, evidence_step: evidenceStep, consent: true })
      if (epoch !== requestEpoch.current) return
      const record = await api.guidance(revision.design_id, accepted.guidance_id)
      if (epoch === requestEpoch.current) setGuidance(record)
    } catch (err) { if (epoch === requestEpoch.current) setError((err as Error).message) }
    finally { if (epoch === requestEpoch.current) setBusy(false) }
  }

  return <Dialog label="AI coach guidance" className="guidance-modal" onClose={onClose}>
    <div className="panel-heading"><h2>AI coach</h2><button onClick={onClose}>Close</button></div>
    <p>Choose a hint, explanation, or direct answer about this draft. Measured results come from simulation.</p>
    <div className="guidance-modes" role="group" aria-label="Guidance mode">{(['hint', 'explain', 'answer'] as const).map(value => <button key={value} disabled={pending} aria-pressed={mode === value} className={mode === value ? 'active' : ''} onClick={() => { setMode(value); setGuidance(null); setSourceHint(null); setError('') }}>{value === 'hint' ? 'Hint' : value === 'explain' ? 'Explain' : 'Answer'}</button>)}</div>
    <label className="field"><span>Focus (optional)</span><input disabled={pending} maxLength={160} value={focus} onChange={event => { setFocus(event.target.value); if (sourceHint) { setSourceHint(null); setGuidance(null) } }} placeholder="A question, component, or requirement"/></label>
    {sourceHint && <div className="guidance-source"><strong>Answering this hint</strong><p>{sourceHint.question}</p></div>}
    <div className="guidance-disclosure"><strong>Before you send</strong><p>The provider receives this challenge’s authored requirements and your saved design. Answers also include the reference explanation and the selected hint, when present. No measured run evidence or credentials are included in this context. Sending is optional.</p></div>
    {!aiConfigured && <p className="status not_evaluated">Provider unavailable. Configure it on the server to use AI guidance.</p>}
    <div className="guidance-actions">{aiConfigured && <button className="primary" disabled={pending} onClick={() => ask()}>{mode === 'hint' ? 'Ask for hint' : mode === 'explain' ? 'Explain this design' : 'Show answer'}</button>}<button className="secondary" onClick={onViewReference}>View reference solution</button></div>
    {busy && <p role="status">Requesting guidance…</p>}
    {error && <p className="finding" role="alert">Guidance unavailable: {error}</p>}
    {guidance && <div className="guidance-answer"><p className={`status ${guidance.status}`}>Guidance {guidance.status} · revision {guidance.revision_id.slice(0,12)}</p>{guidance.status === 'failed' ? <><p>AI guidance unavailable. Your draft and simulation controls remain available.</p>{[...new Set([guidance.error, ...guidance.validation_errors].filter(Boolean))].map((message,i) => <p key={i}>{message}</p>)}</> : guidance.status === 'completed' ? <><h3>{guidance.mode === 'hint' ? 'A question to consider' : guidance.mode === 'answer' ? 'Answer' : 'Explanation'}</h3>{guidance.question && <p>{guidance.question}</p>}{guidance.explanation && <p>{guidance.explanation}</p>}{guidance.authored_refs.length > 0 && <small>Authored sources: {guidance.authored_refs.join(', ')}</small>}{guidance.mode === 'hint' && <div className="guidance-actions">{!guidance.evidence_step && <button className="secondary" disabled={pending} onClick={() => ask('hint', true)}>Show explanation</button>}<button className="secondary" disabled={pending} onClick={() => ask('answer', false, guidance)}>Show answer</button></div>}</> : <p>Waiting for the provider. The saved draft remains available.</p>}</div>}
  </Dialog>
}
