import type { Design, Trace } from '../api/client'

type Point = { timeUs: number; playMs: number }

export function createTimeline(times: number[], teaching: boolean): Point[] {
  let playMs = 0
  const sorted = [...new Set(times)].sort((a, b) => a - b)
  return sorted.map((timeUs, index) => {
    if (index) playMs += Math.max(teaching ? 750 : 0, (timeUs - sorted[index - 1]) / 1000)
    return { timeUs, playMs }
  })
}

export function recordedAt(points: Point[], playMs: number): number {
  if (!points.length) return 0
  const next = points.findIndex(point => point.playMs > playMs)
  if (next === 0) return points[0].timeUs
  if (next === -1) return points.at(-1)!.timeUs
  const a = points[next - 1], b = points[next]
  return a.timeUs + (b.timeUs - a.timeUs) * (playMs - a.playMs) / (b.playMs - a.playMs)
}

export function playheadAt(points: Point[], timeUs: number): number {
  if (!points.length) return 0
  const next = points.findIndex(point => point.timeUs > timeUs)
  if (next === 0) return 0
  if (next === -1) return points.at(-1)!.playMs
  const a = points[next - 1], b = points[next]
  return a.playMs + (b.playMs - a.playMs) * (timeUs - a.timeUs) / (b.timeUs - a.timeUs)
}

export function explainEvent(event: Trace['events'][number] | undefined, design: Design): string {
  if (!event) return 'Choose Play or Next frame to follow this recorded request.'
  const label = (id: string | null | undefined) => design.nodes.find(node => node.id === id)?.label || 'the component'
  const node = label(event.node_id)
  const edge = design.edges.find(edge => edge.id === event.edge_id)
  if (edge && event.event === 'downstream_started') return `${label(edge.source)} sends the request to ${label(edge.target)}.`
  if (edge && event.event === 'response_sent') return `${label(edge.target)} sends its response back to ${label(edge.source)}.`
  switch (event.event) {
    case 'arrived': return `The request reaches ${node}.`
    case 'queued': return `${node} is busy. This request waits for a free processing slot.`
    case 'service_started': return `${node} starts processing the request.`
    case 'service_finished': return `${node} finishes its processing work.`
    case 'cache_hit': return `${node} has the requested data in its cache.`
    case 'cache_miss': return `${node} does not have the data; the request needs the next component.`
    case 'terminal_outcome': return event.details?.status === 'success'
      ? 'The response returned to the client successfully.'
      : `The request ended with ${String(event.details?.status || 'an unavailable outcome').replaceAll('_', ' ')}.`
    case 'retry_scheduled': return `${node} will retry its downstream request after a delay.`
    default: return `${node}: ${event.event.replaceAll('_', ' ')}.`
  }
}
