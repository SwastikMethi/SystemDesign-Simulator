import { Fragment, useEffect, useState } from 'react'
import { api, type Challenge, type ReferenceAnswer } from '../api/client'
import { Dialog } from '../Dialog'
import { RecordedGraph } from '../results/RecordedGraph'

export function ReferenceSolution({ challenge, onClose }: { challenge: Challenge; onClose: () => void }) {
  const [answer, setAnswer] = useState<ReferenceAnswer | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setAnswer(null); setError('')
    api.reference(challenge.challenge_id).then(value => { if (active) setAnswer(value) }).catch(err => { if (active) setError((err as Error).message) })
    return () => { active = false }
  }, [challenge.challenge_id, attempt])

  return <Dialog label="Reference solution" className="reference-modal" onClose={onClose}>
    <div className="panel-heading"><div><p className="eyebrow">{challenge.title} · Read-only reference</p><h2>Reference solution</h2></div><button onClick={onClose}>Close</button></div>
    <p className="muted">One acceptable approach. Completion comes from assessing your own design.</p>
    {error ? <><p className="finding" role="alert">{error}</p><button className="secondary" onClick={() => setAttempt(current => current + 1)}>Retry</button></> : !answer ? <p role="status">Loading reference solution…</p> : <>
      <RecordedGraph design={answer.design} timeUs={0} label="Reference architecture" caption="Reference approach · Read-only" />
      <section className="reference-explanation"><h3>How it works</h3>{answer.explanation.split('\n\n').map((paragraph, index) => <p key={index}>{paragraph}</p>)}</section>
      <section><h3>Components and settings</h3><div className="reference-components">{answer.design.nodes.map(node => <article className="reference-component" key={node.id}>
        <h4>{node.label}</h4><p className="muted">{node.type.replaceAll('_', ' ')}</p>
        <dl><dt>Profile</dt><dd>{node.profile_id}</dd><dt>Instances</dt><dd>{node.instance_count}</dd>{Object.entries(node.settings).map(([key, value]) => <Fragment key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value)}</dd></Fragment>)}</dl>
        <small className="muted">Unlisted settings use the model defaults.</small>
      </article>)}</div></section>
      <section className="reference-connections"><h3>Connections</h3><ul>{answer.design.edges.map(edge => <li key={edge.id}>
        <strong>{answer.design.nodes.find(node => node.id === edge.source)?.label} → {answer.design.nodes.find(node => node.id === edge.target)?.label}</strong>
        <span>{edge.kind.replaceAll('_', ' ')} · {edge.operation_ids.join(', ')}</span>
      </li>)}</ul></section>
    </>}
  </Dialog>
}
