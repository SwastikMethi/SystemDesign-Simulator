import { useEffect, useState } from 'react'
import type { Design, Guidance } from '../api/client'
import { api } from '../api/client'

type Props = { aiConfigured: boolean; onClose: () => void; saveDesign: () => Promise<Design | null> }

export function GuidancePanel({ aiConfigured, onClose, saveDesign }: Props) {
  const [mode, setMode] = useState<'hint' | 'explain'>('hint')
  const [focus, setFocus] = useState('')
  const [guidance, setGuidance] = useState<Guidance | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!guidance || guidance.status !== 'queued') return
    const timer = window.setInterval(() => api.guidance(guidance.design_id, guidance.guidance_id).then(setGuidance).catch(err => setError((err as Error).message)), 1500)
    return () => window.clearInterval(timer)
  }, [guidance?.design_id, guidance?.guidance_id, guidance?.status])

  const ask = async (evidenceStep = false) => {
    setBusy(true); setError('')
    try {
      const revision = await saveDesign()
      if (!revision) { setError('Save the draft before requesting guidance.'); return }
      const accepted = await api.startGuidance(revision.design_id, { revision_id: revision.revision_id, mode, focus: evidenceStep ? guidance?.focus || null : focus.trim() || null, evidence_step: evidenceStep, consent: true })
      setGuidance(await api.guidance(revision.design_id, accepted.guidance_id))
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal guidance-modal" role="dialog" aria-modal="true" aria-label="AI coach guidance" onMouseDown={event => event.stopPropagation()}>
    <div className="panel-heading"><h2>AI coach</h2><button onClick={onClose}>Close</button></div>
    <p>Ask about this saved draft before running it. Guidance can explain authored requirements or ask a question; measured results still come only from simulation.</p>
    <div className="guidance-modes" role="group" aria-label="Guidance mode"><button className={mode === 'hint' ? 'active' : ''} onClick={() => { setMode('hint'); setGuidance(null) }}>Hint</button><button className={mode === 'explain' ? 'active' : ''} onClick={() => { setMode('explain'); setGuidance(null) }}>Explain</button></div>
    <label className="field"><span>Focus (optional)</span><input maxLength={160} value={focus} onChange={event => setFocus(event.target.value)} placeholder="A component or requirement to discuss"/></label>
    <div className="guidance-disclosure"><strong>Before you send</strong><p>The provider receives this challenge’s authored requirements and your saved design. No measured run evidence or credentials are sent. Sending is optional.</p></div>
    {!aiConfigured && <p className="status not_evaluated">Provider unavailable. Configure it on the server to use AI guidance.</p>}
    {aiConfigured && <button className="primary" disabled={busy || guidance?.status === 'queued'} onClick={() => ask(false)}>{mode === 'hint' ? 'Ask for hint' : 'Explain this design'}</button>}
    {error && <p className="finding" role="alert">Guidance unavailable: {error}</p>}
    {guidance && <div className="guidance-answer"><p className={`status ${guidance.status}`}>Guidance {guidance.status} · revision {guidance.revision_id.slice(0,12)}</p>{guidance.status === 'failed' ? <><p>AI guidance unavailable. Your draft and simulation controls remain available.</p><p>{guidance.error}</p>{guidance.validation_errors.length > 0 && <ul>{guidance.validation_errors.map((message,i) => <li key={i}>{message}</li>)}</ul>}</> : guidance.status === 'completed' ? <><h3>{guidance.mode === 'hint' ? 'A question to consider' : 'Explanation'}</h3>{guidance.question && <p>{guidance.question}</p>}{guidance.explanation && <p>{guidance.explanation}</p>}{guidance.authored_refs.length > 0 && <small>Authored sources: {guidance.authored_refs.join(', ')}</small>}{guidance.mode === 'hint' && !guidance.evidence_step && <button className="secondary" disabled={busy} onClick={() => ask(true)}>Show explanation</button>}</> : <p>Waiting for the provider. The saved draft remains available.</p>}</div>}
  </div></div>
}
