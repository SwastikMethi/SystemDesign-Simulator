import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { SuggestedExperiment } from './ExperimentView'
import { outcomeKey } from './evidence'

describe('result identity and coach experiments', () => {
  it('keeps evidence for the same requirement on different operations separate', () => {
    expect(outcomeKey({ requirement_id: 'R01', operation_id: 'read' })).not.toBe(outcomeKey({ requirement_id: 'R01', operation_id: 'write' }))
  })

  it('renders a completed review experiment with its string tradeoff', () => {
    const html = renderToStaticMarkup(<SuggestedExperiment proposal={{ purpose: 'Move reads through cache', expected_tradeoffs: 'Lower read latency with higher memory cost', patch: { nodes: [] } }} index={0} busy={false} onTest={() => {}}/>)
    expect(html).toContain('Lower read latency with higher memory cost')
    expect(html).toContain('Test proposal')
  })
})
