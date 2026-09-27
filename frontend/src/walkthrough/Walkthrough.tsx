import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { Run } from '../api/client'
import type { LessonStep } from './lesson'
import './Walkthrough.css'

const steps: Record<LessonStep, { title: string; body: string; target: string; tab?: string }> = {
  client: { title: 'Add a client', body: 'In Components, choose Client. This represents the person or application asking for a note.', target: 'add-client', tab: 'architecture' },
  app: { title: 'Add the application', body: 'In Components, choose App service. It receives the client’s request and asks the database for the note.', target: 'add-app_service', tab: 'architecture' },
  database: { title: 'Add a database', body: 'In Components, choose SQL database. It stores the notes. Keep the small default profile for this first attempt.', target: 'add-sql_database', tab: 'architecture' },
  'client-route': { title: 'Connect Client to App service', body: 'In Inspector → Add connection, choose From: Client and To: App service. Keep Relationship: request, check read_note, then choose Add connection. You can also drag between their ports.', target: 'connection', tab: 'architecture' },
  'database-route': { title: 'Connect App service to SQL database', body: 'Choose From: App service and To: SQL database. Keep Relationship: request, check read_note, then choose Add connection. Now the application can fetch a note.', target: 'connection', tab: 'architecture' },
  requirements: { title: 'Know what success means', body: 'R01 checks successful requests. R02 limits how long most successful reads take. R03 keeps the design within its cost budget. All three must pass.', target: 'requirements', tab: 'requirements' },
  preview: { title: 'Try the first design', body: 'Choose Preview to send traffic through your architecture. Your draft is saved automatically. This first database is deliberately small, so use the result to find what needs improving.', target: 'preview' },
  flow: { title: 'Follow one request', body: 'Choose Play, or use Next frame. Watch the highlighted connections and components: Client → App service → SQL database, then the response back. The explanation above the diagram follows the recorded events.', target: 'replay', tab: 'results' },
  evidence: { title: 'Find the slow requests', body: 'In R02, choose Inspect evidence. The latency target is 250 ms. The small database cannot keep up with this workload; requests queue while waiting for it. Read the aggregate result alongside the individual request.', target: 'latency-evidence', tab: 'results' },
  upgrade: { title: 'Give the database more capacity', body: 'Select the SQL database’s Profile in the Inspector and choose sql.medium.v1. The guide selects the database for you. This adds capacity while keeping the total cost under 50 credits per hour.', target: 'database-profile', tab: 'architecture' },
  assessment: { title: 'Assess the improved design', body: 'Choose Assess design to check success, latency and cost together. Only a completed, passing assessment of this revision finishes the walkthrough.', target: 'assess' },
  complete: { title: 'Your first design passes', body: 'The client reaches the application, the application reads from the database, and the response returns. The larger database meets the targets within budget. Open Saved work to revisit this assessment.', target: 'saved-work' },
}

type Props = { step: LessonStep; tab: string; run: Run | null; starting: boolean; onReadRequirements: () => void; onClose: () => void; onRestart: () => void }
type Rect = { top: number; left: number; width: number; height: number }

export function Walkthrough({ step, tab, run, starting, onReadRequirements, onClose, onRestart }: Props) {
  const info = steps[step]
  const otherTab = info.tab && tab !== info.tab
  const waiting = ['preview', 'assessment'].includes(step) && (starting || run?.execution_status === 'queued' || run?.execution_status === 'running')
  const target = otherTab ? `tab-${info.tab}` : waiting ? 'run-status' : info.target
  const [rect, setRect] = useState<Rect | null>(null)
  const [position, setPosition] = useState({ top: 160, left: 24 })
  const card = useRef<HTMLElement>(null)
  const number = Object.keys(steps).indexOf(step) + 1

  useLayoutEffect(() => {
    let element: HTMLElement | undefined
    let frame = 0
    let focused = false
    const update = () => {
      const found = [...document.querySelectorAll<HTMLElement>(`[data-guide="${target}"]`)].find(node => node.getBoundingClientRect().width && node.getBoundingClientRect().height)
      if (!found) { setRect(null); return }
      if (element !== found) {
        element?.removeAttribute('aria-describedby')
        element = found
        element.setAttribute('aria-describedby', 'walkthrough-instruction')
        element.scrollIntoView({ block: step === 'flow' ? 'start' : 'nearest', inline: 'nearest', behavior: 'instant' })
      }
      const box = element.getBoundingClientRect()
      const bounds = { top: Math.max(8, box.top - 4), left: Math.max(8, box.left - 4), width: Math.min(box.width + 8, innerWidth - 16), height: Math.min(box.bottom + 4, innerHeight - 8) - Math.max(8, box.top - 4) }
      if (bounds.height <= 0) { setRect(null); return }
      setRect(bounds)
      const width = card.current?.offsetWidth || 280, height = card.current?.offsetHeight || 300
      let left = box.right + 16, top = Math.max(16, box.top)
      if (left + width > innerWidth - 16) {
        left = box.left - width - 16
        if (left < 16) {
          left = innerWidth - width - 16
          top = box.bottom + 16 + height <= innerHeight ? box.bottom + 16 : box.top - height - 16
        }
      }
      setPosition({ left: Math.max(16, left), top: Math.max(16, Math.min(top, innerHeight - height - 16)) })
      if (!focused) {
        const control = step === 'flow' ? element.querySelector<HTMLElement>('[data-guide="play"]') : element.matches('button, select, input, [tabindex]') ? element : element.querySelector<HTMLElement>('button, select, input')
        if (control && !control.matches(':disabled')) { control.focus({ preventScroll: true }); focused = true }
      }
    }
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(update) }
    const resize = new ResizeObserver(schedule)
    resize.observe(document.body)
    if (card.current) resize.observe(card.current)
    // The editor can open a drawer or render the target after the guide mounts.
    const observer = new MutationObserver(schedule)
    observer.observe(document.querySelector('main') || document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'disabled'] })
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, true)
    update()
    return () => { cancelAnimationFrame(frame); resize.disconnect(); observer.disconnect(); window.removeEventListener('resize', schedule); window.removeEventListener('scroll', schedule, true); element?.removeAttribute('aria-describedby') }
  }, [target, step])

  return createPortal(<>
    {rect && <div className={`guide-spotlight ${step === 'flow' ? 'guide-flow' : ''}`} style={rect} aria-hidden="true" />}
    <aside ref={card} className="walkthrough-guide" role="dialog" aria-label="First design guide" aria-modal="false" data-step={step} style={position} onKeyDown={event => { if (event.key === 'Escape') onClose() }}>
      <div className="guide-progress"><span>FIRST DESIGN</span><span>{number} / {Object.keys(steps).length}</span></div>
      <h2>{otherTab ? `Open ${info.tab === 'architecture' ? 'Architecture' : info.tab === 'requirements' ? 'Requirements' : 'Results'}` : waiting ? 'Your simulation is running' : info.title}</h2>
      <p id="walkthrough-instruction">{otherTab ? `Choose the ${info.tab} tab. ${info.body}` : waiting ? 'Wait for the simulation to finish. If you cancel, you can try this step again.' : info.body}</p>
      {!waiting && ['failed', 'canceled', 'interrupted'].includes(run?.execution_status || '') && ['preview', 'assessment'].includes(step) && <p className="guide-recovery">The last run {run?.execution_status}. Choose {step === 'preview' ? 'Preview' : 'Assess design'} to try again.</p>}
      {step === 'requirements' && !otherTab && <button className="primary full" onClick={onReadRequirements}>Continue to Preview</button>}
      {step === 'complete' && <button className="primary full" onClick={onClose}>Finish guide</button>}
      <div className="guide-actions"><button onClick={onClose}>Skip guide</button><button onClick={onRestart}>Restart walkthrough</button></div>
    </aside>
  </>, document.body)
}
