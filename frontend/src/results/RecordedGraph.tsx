import { useLayoutEffect, useMemo } from 'react'
import { Background, BaseEdge, Handle, Position, ReactFlow, getStraightPath, useNodesState, type Edge, type EdgeProps, type Node, type NodeProps, type NodeTypes } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { Design, DesignEdge, DesignNode, Snapshot, Trace } from '../api/client'
import './RecordedGraph.css'

type Props = {
  design: Design
  baseline?: Design
  snapshot?: Snapshot
  trace?: Trace
  timeUs: number
  playing?: boolean
  reducedMotion?: boolean
}
type Change = 'added' | 'removed' | 'changed' | 'same'
type GraphNode = Node<{ design: DesignNode; state?: Record<string, number>; change: Change; changes: string[]; event?: string }, 'recorded'>
type GraphEdge = Edge<{ change: Change; changes: string[]; event?: string; progress?: number; reducedMotion: boolean }, 'recorded'>

const words = (value: string) => value.replaceAll('_', ' ')
const eventTone = (event: string) => event === 'cache_hit' || event === 'fault_ended' ? 'pass' : event === 'cache_miss' ? 'warn' : /rejected|failed|timed_out|fault_started|deadline_missed/.test(event) ? 'fail' : ''
const nodeChanges = (current: DesignNode, before: DesignNode): string[] => {
  const changes: string[] = []
  if (current.type !== before.type) changes.push(`type ${words(before.type)} → ${words(current.type)}`)
  if (current.label !== before.label) changes.push(`name ${before.label} → ${current.label}`)
  if (current.profile_id !== before.profile_id) changes.push(`profile ${before.profile_id} → ${current.profile_id}`)
  if (current.instance_count !== before.instance_count) changes.push(`instances ${before.instance_count} → ${current.instance_count}`)
  const oldSettings = before.settings as Record<string, unknown>
  const newSettings = current.settings as Record<string, unknown>
  for (const key of new Set([...Object.keys(oldSettings), ...Object.keys(newSettings)])) {
    if (JSON.stringify(oldSettings[key]) !== JSON.stringify(newSettings[key])) changes.push(`${words(key)} ${String(oldSettings[key] ?? 'default')} → ${String(newSettings[key] ?? 'default')}`)
  }
  if (current.position.x !== before.position.x || current.position.y !== before.position.y) changes.push('position')
  return changes
}
const edgeChanges = (current: DesignEdge, before: DesignEdge): string[] => {
  const changes: string[] = []
  if (current.source !== before.source || current.target !== before.target) changes.push(`route ${before.source} → ${before.target} to ${current.source} → ${current.target}`)
  if (current.kind !== before.kind) changes.push(`relationship ${words(before.kind)} → ${words(current.kind)}`)
  if ([...current.operation_ids].sort().join('\0') !== [...before.operation_ids].sort().join('\0')) changes.push(`operations ${before.operation_ids.join(', ')} → ${current.operation_ids.join(', ')}`)
  return changes
}
const count = (state: Record<string, number> | undefined, key: string) => state && Object.hasOwn(state, key) ? state[key] : undefined

function RecordedNode({ data }: NodeProps<GraphNode>) {
  const { design, state, change, changes, event } = data
  const counters = [
    ['Busy', 'busy_slots'], ['Available', 'available_slots'], ['Unavailable', 'unavailable_slots'], ['Queue', 'queue_depth'],
    ['Backlog', 'backlog'], ['Accepted pending', 'accepted_pending'],
    ['Cache hits', 'cache_hits'], ['Cache misses', 'cache_misses'],
  ] as const
  return <div className={`recorded-node recorded-${change} ${event ? 'recorded-active' : ''}`} title={`${design.label}: ${change}${changes.length ? ` (${changes.join(', ')})` : ''}`}>
    <Handle type="target" position={Position.Left} isConnectable={false} />
    <span className="recorded-node-type">{words(design.type)}</span>
    <strong>{design.label}</strong>
    <span className="recorded-node-profile">{design.profile_id} · {design.instance_count} {design.instance_count === 1 ? 'instance' : 'instances'}</span>
    {change !== 'same' && <span className={`recorded-change recorded-${change}`}>{change === 'changed' ? `Changed: ${changes.join(', ')}` : change}</span>}
    {event && <span className={`recorded-event ${eventTone(event)}`}>{eventTone(event) === 'fail' ? '! ' : ''}{words(event)}</span>}
    {state && <div className="recorded-counters">{counters.map(([label, key]) => count(state, key) === undefined ? null : <span key={key}>{label} <b>{count(state, key)}</b></span>)}</div>}
    <Handle type="source" position={Position.Right} isConnectable={false} />
  </div>
}

function RecordedEdge({ sourceX, sourceY, targetX, targetY, markerEnd, data }: EdgeProps<GraphEdge>) {
  const [path] = getStraightPath({ sourceX, sourceY, targetX, targetY })
  const progress = data?.progress
  return <>
    <BaseEdge path={path} markerEnd={markerEnd} className={`recorded-edge recorded-${data?.change || 'same'} ${data?.event ? 'recorded-active' : ''}`} />
    {progress !== undefined && !data?.reducedMotion && <circle className="recorded-marker" cx={sourceX + (targetX - sourceX) * progress} cy={sourceY + (targetY - sourceY) * progress} r="5" />}
  </>
}

const nodeTypes: NodeTypes = { recorded: RecordedNode }
const edgeTypes = { recorded: RecordedEdge }

export function RecordedGraph({ design, baseline, snapshot, trace, timeUs, playing = false, reducedMotion = false }: Props) {
  const { nodes, edges, descriptions, currentEvent } = useMemo(() => {
    const priorNodes = new Map(baseline?.nodes.map(node => [node.id, node]) || [])
    const priorEdges = new Map(baseline?.edges.map(edge => [edge.id, edge]) || [])
    const currentNodeIds = new Set(design.nodes.map(node => node.id))
    const currentEdgeIds = new Set(design.edges.map(edge => edge.id))
    const events = trace?.events.filter(event => event.time_us <= timeUs) || []
    const latest = events.at(-1)
    const activeNode = latest?.node_id || (latest?.event === 'terminal_outcome' ? design.nodes.find(node => node.type === 'client')?.id : undefined)
    const activeEdge = latest?.edge_id || undefined
    const transfer = activeEdge && latest && (latest.event === 'downstream_started' || latest.event === 'response_sent') ? latest : undefined
    const wait = transfer ? Number(transfer.details?.queue_wait_us || 0) : 0
    const travel = transfer ? Number(transfer.details?.transfer_us || 0) + Number(transfer.details?.propagation_us || 0) : 0
    const duration = wait + travel
    const progress = transfer && travel > 0 && timeUs <= transfer.time_us + duration
      ? (transfer.event === 'response_sent' ? 1 - Math.max(0, Math.min(1, (timeUs - transfer.time_us - wait) / travel)) : Math.max(0, Math.min(1, (timeUs - transfer.time_us - wait) / travel)))
      : undefined
    const graphNodes: GraphNode[] = [...design.nodes, ...(baseline?.nodes.filter(node => !currentNodeIds.has(node.id)) || [])].map(node => {
      const before = priorNodes.get(node.id)
      const removed = !currentNodeIds.has(node.id)
      const changes = before && !removed ? nodeChanges(node, before) : []
      const change: Change = !baseline ? 'same' : removed ? 'removed' : !before ? 'added' : changes.length ? 'changed' : 'same'
      return { id: node.id, type: 'recorded', position: node.position, draggable: false, selectable: false,
        data: { design: node, state: removed ? undefined : snapshot?.nodes[node.id], change, changes, event: !removed && activeNode === node.id ? latest?.event : undefined } }
    })
    const graphEdges: GraphEdge[] = [...design.edges, ...(baseline?.edges.filter(edge => !currentEdgeIds.has(edge.id)) || [])].map(edge => {
      const before = priorEdges.get(edge.id)
      const removed = !currentEdgeIds.has(edge.id)
      const changes = before && !removed ? edgeChanges(edge, before) : []
      const change: Change = !baseline ? 'same' : removed ? 'removed' : !before ? 'added' : changes.length ? 'changed' : 'same'
      return { id: edge.id, type: 'recorded', source: edge.source, target: edge.target,
        label: `${words(edge.kind)}${changes.length ? ' · changed' : ''}`,
        selectable: false, markerEnd: { type: 'arrowclosed' },
        data: { change, changes, event: !removed && activeEdge === edge.id ? latest?.event : undefined, progress: !removed && activeEdge === edge.id ? progress : undefined, reducedMotion } }
    })
    const nodeNames = new Map(graphNodes.map(node => [node.id, node.data.design.label]))
    const descriptions = [
      ...graphNodes.map(node => `${node.data.design.label}, ${words(node.data.design.type)}, ${node.data.change}${node.data.changes.length ? ` (${node.data.changes.join(', ')})` : ''}${node.data.state ? `; ${Object.entries(node.data.state).map(([key, value]) => `${words(key)} ${value}`).join(', ')}` : ''}${node.data.event ? `; ${words(node.data.event)}` : ''}`),
      ...graphEdges.map(edge => `${nodeNames.get(edge.source) || edge.source} to ${nodeNames.get(edge.target) || edge.target}, ${String(edge.label)}, ${edge.data?.change}${edge.data?.changes.length ? ` (${edge.data.changes.join(', ')})` : ''}${edge.data?.event ? `; ${words(edge.data.event)}` : ''}`),
    ]
    const currentEvent = latest ? `${words(latest.event)}${typeof latest.details?.status === 'string' ? ` · ${latest.details.status}` : ''}` : undefined
    return { nodes: graphNodes, edges: graphEdges, descriptions, currentEvent }
  }, [design, baseline, snapshot, trace, timeUs, reducedMotion])
  const [renderedNodes, setNodes, onNodesChange] = useNodesState(nodes)
  useLayoutEffect(() => {
    setNodes(previous => {
      const measured = new Map(previous.map(node => [node.id, node.measured]))
      // Keep React Flow's measurements when animation changes node data.
      return nodes.map(node => ({ ...node, measured: measured.get(node.id) }))
    })
  }, [nodes, setNodes])

  return <section className={`recorded-graph ${playing ? 'recorded-playing' : ''}`} aria-label="Recorded architecture">
    <div className="recorded-canvas" aria-hidden="true">
      <ReactFlow key={`${design.revision_id}:${baseline?.revision_id || ''}`} nodes={renderedNodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} fitView fitViewOptions={{ padding: .16 }} minZoom={.25} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} zoomOnDoubleClick={false} proOptions={{ hideAttribution: true }}>
        <Background color="var(--grid)" gap={20} size={1} />
      </ReactFlow>
    </div>
    <div className="recorded-legend" aria-label="Architecture legend">
      <span>Recorded revision {design.revision_id}</span>
      <span>Drag canvas to inspect connections</span>
      {baseline && <><span className="recorded-added">+ Added</span><span className="recorded-removed">− Removed</span><span className="recorded-changed">~ Changed</span></>}
      {trace && <span>{trace.operation_id} · {trace.request_id} · {Math.max(0, timeUs / 1000).toFixed(2)} ms{currentEvent ? ` · ${currentEvent}` : ''}</span>}
      {reducedMotion && <span>Reduced motion</span>}
    </div>
    <details className="recorded-list"><summary>Architecture list · {nodes.length} components, {edges.length} connections</summary><ul>{descriptions.map((description, index) => <li key={index}>{description}</li>)}</ul></details>
  </section>
}
