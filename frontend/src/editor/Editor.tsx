import { useEffect, useMemo, useRef, useState } from 'react'
import { ReactFlow, Background, Controls, Handle, Position, type Connection, type Node, type Edge, type NodeProps, type NodeTypes, type ReactFlowInstance } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Dialog } from '../Dialog'
import { Copy, Plus, RotateCcw, RotateCw, Trash2 } from 'lucide-react'
import type { Catalogue, Challenge, DesignEdge, DesignNode, Profile, Validation } from '../api/client'
import { addEdge, addNode, duplicateNode, removeNode, updateEdge, updateNode, type Graph } from './graph'
import type { LessonStep } from '../walkthrough/lesson'

type Props = { challenge: Challenge; catalogue: Catalogue; graph: Graph; commit: (next: Graph) => void; undo: () => void; redo: () => void; canUndo: boolean; canRedo: boolean; validation: Validation | null; onError: (message: string) => void; activeOperation: string; setActiveOperation: (id: string) => void; guideStep?: LessonStep }
type LabData = { node: DesignNode; profile?: Profile; state?: string }

function LabNode({ data, selected }: NodeProps<Node<LabData>>) {
  const { node, profile } = data
  return <div className={`lab-node ${selected ? 'selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <div className="node-type">{node.type.replaceAll('_', ' ')}</div>
    <strong title={node.label}>{node.label}</strong>
    <small>{node.profile_id} · {node.instance_count} {node.instance_count === 1 ? 'instance' : 'instances'}</small>
    <span className="node-support">● {data.state || profile?.support_label || 'Simulated'}</span>
    <Handle type="source" position={Position.Right} />
  </div>
}
const nodeTypes: NodeTypes = { lab: LabNode }

export function Editor({ challenge, catalogue, graph, commit, undo, redo, canUndo, canRedo, validation, onError, activeOperation, setActiveOperation, guideStep }: Props) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null)
  const [paletteSearch, setPaletteSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [connectKind, setConnectKind] = useState<DesignEdge['kind']>('request')
  const [manualSource, setManualSource] = useState('')
  const [manualTarget, setManualTarget] = useState('')
  const [manualOperations, setManualOperations] = useState<string[]>([])
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [dragPositions, setDragPositions] = useState<Record<string, { x: number; y: number }>>({})
  const flow = useRef<ReactFlowInstance<Node<LabData>, Edge> | null>(null)
  useEffect(() => {
    if (!guideStep || !graph.nodes.length) return
    const frame = requestAnimationFrame(() => { void flow.current?.fitView({ padding: .22 }) })
    return () => cancelAnimationFrame(frame)
  }, [guideStep, graph.nodes.length])
  useEffect(() => {
    if (!guideStep) return
    const adding = ['client', 'app', 'database'].includes(guideStep)
    setPaletteOpen(adding); setInspectorOpen(!adding)
    if (adding) setPaletteSearch('')
    if (guideStep === 'client-route' || guideStep === 'database-route') {
      setSelectedNode(null); setSelectedEdge(null); setManualSource(''); setManualTarget(''); setManualOperations([]); setConnectKind('request')
    }
    if (guideStep === 'upgrade') { setSelectedNode(graph.nodes.find(node => node.type === 'sql_database')?.id || null); setSelectedEdge(null) }
  }, [guideStep])
  const selected = graph.nodes.find(n => n.id === selectedNode)
  const edgeSelected = graph.edges.find(e => e.id === selectedEdge)
  const allowed = catalogue.component_types
  const visible = allowed.filter(c => `${c.label} ${c.purpose}`.toLowerCase().includes(paletteSearch.toLowerCase()))
  const flowNodes = useMemo<Node<LabData>[]>(() => graph.nodes.map(node => ({ id: node.id, type: 'lab', position: dragPositions[node.id] || node.position, data: { node, profile: catalogue.profiles.find(p => p.id === node.profile_id) }, selected: node.id === selectedNode })), [graph.nodes, catalogue.profiles, selectedNode, dragPositions])
  const flowEdges = useMemo<Edge[]>(() => graph.edges.map(edge => ({ id: edge.id, source: edge.source, target: edge.target, label: `${edge.kind.replaceAll('_', ' ')} · ${edge.operation_ids.join(', ')}`, selected: edge.id === selectedEdge, className: `${edge.kind} ${activeOperation !== 'all' && !edge.operation_ids.includes(activeOperation) ? 'dimmed' : ''}`, animated: false })), [graph.edges, selectedEdge, activeOperation])
  const perform = (action: () => Graph) => { try { commit(action()) } catch (error) { onError((error as Error).message) } }
  const add = (type: DesignNode['type']) => { perform(() => addNode(graph, type, catalogue, challenge.challenge_id === 'first-design' ? { x: ['client', 'app_service', 'sql_database'].indexOf(type) * 320, y: 180 } : undefined)); setShowAdd(false); if (!guideStep) setPaletteOpen(false) }
  const connect = (source: string, target: string) => perform(() => addEdge(graph, source, target, connectKind, manualOperations.length ? manualOperations : activeOperation === 'all' ? challenge.operations.map(o => o.id) : [activeOperation], challenge))
  const onConnect = (connection: Connection) => { if (connection.source && connection.target) connect(connection.source, connection.target) }
  const removeSelected = () => {
    if (selectedNode) {
      const count = graph.edges.filter(e => e.source === selectedNode || e.target === selectedNode).length
      if (count && !window.confirm(`Delete ${selected?.label} and its ${count} connected ${count === 1 ? 'route' : 'routes'}?`)) return
      commit(removeNode(graph, selectedNode)); setSelectedNode(null)
    } else if (selectedEdge) { commit({ ...graph, edges: graph.edges.filter(e => e.id !== selectedEdge) }); setSelectedEdge(null) }
  }
  return <div className="editor-layout">
    <aside className={`palette side-panel ${paletteOpen ? 'open' : ''}`} aria-label="Component palette">
      <div className="panel-heading"><h2>Components</h2><button className="mobile-close" onClick={() => setPaletteOpen(false)}>Close</button></div>
      <p className="muted">Drag a route between ports, or use Add connection.</p>
      <label className="field"><span>Search components</span><input value={paletteSearch} onChange={e => setPaletteSearch(e.target.value)} placeholder="Find a block" /></label>
      <div className="palette-list">{visible.map(component => <button data-guide={`add-${component.type}`} key={component.type} className="palette-item" disabled={!challenge.allowed_component_types.includes(component.type as DesignNode['type'])} onClick={() => add(component.type as DesignNode['type'])}><Plus size={16}/><span><strong>{component.label}</strong><small>{challenge.allowed_component_types.includes(component.type as DesignNode['type']) ? component.purpose : 'Not allowed in this challenge'}</small></span></button>)}</div>
      <button className="secondary full" onClick={() => setShowAdd(true)}>Add component by keyboard</button>
    </aside>
    <section className="canvas-column" aria-label="Architecture editor">
      <div className="canvas-toolbar">
        <div className="toolbar-group mobile-tools"><button onClick={() => setPaletteOpen(true)}>Components</button><button onClick={() => setInspectorOpen(true)}>Inspector</button></div>
        <label>Show routes <select value={activeOperation} onChange={e => setActiveOperation(e.target.value)}><option value="all">All operations</option>{challenge.operations.map(o => <option key={o.id} value={o.id}>{o.id}</option>)}</select></label>
        <div className="toolbar-group"><button title="Undo" aria-label="Undo" disabled={!canUndo} onClick={undo}><RotateCcw size={17}/></button><button title="Redo" aria-label="Redo" disabled={!canRedo} onClick={redo}><RotateCw size={17}/></button><button title="Duplicate selection" aria-label="Duplicate selection" disabled={!selectedNode} onClick={() => selectedNode && perform(() => duplicateNode(graph, selectedNode))}><Copy size={17}/></button><button title="Delete selection" aria-label="Delete selection" disabled={!selectedNode && !selectedEdge} onClick={removeSelected}><Trash2 size={17}/></button></div>
      </div>
      <div className="flow-wrap" onKeyDown={e => { if ((e.key === 'Delete' || e.key === 'Backspace') && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) removeSelected() }}>
        <ReactFlow onInit={instance => { flow.current = instance }} nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} onConnect={onConnect} onNodeClick={(_, node) => { setSelectedNode(node.id); setSelectedEdge(null); setInspectorOpen(true) }} onEdgeClick={(_, edge) => { setSelectedEdge(edge.id); setSelectedNode(null); setInspectorOpen(true) }} onPaneClick={() => { setSelectedNode(null); setSelectedEdge(null) }} onNodeDrag={(_, node) => setDragPositions(current => ({ ...current, [node.id]: node.position }))} onNodeDragStop={(_, node) => { commit(updateNode(graph, node.id, { position: node.position })); setDragPositions({}) }} fitView fitViewOptions={{ padding: .22 }} minZoom={.25} maxZoom={1.6} nodesDraggable snapToGrid snapGrid={[16,16]}>
          <Background color="var(--grid)" gap={20} size={1} /><Controls showInteractive={false}/>
        </ReactFlow>
        {graph.nodes.length === 0 && <div className="canvas-empty"><strong>Start with a client</strong><p>Add components, then connect one route for every operation.</p><button className="primary" onClick={() => add('client')}>Add client</button></div>}
      </div>
      <div className="graph-list"><details><summary>Architecture list · {graph.nodes.length} components, {graph.edges.length} connections</summary><ul>{graph.nodes.map(n => <li key={n.id}><button onClick={() => { setSelectedNode(n.id); setSelectedEdge(null); setInspectorOpen(true) }}>{n.label} · {n.type.replaceAll('_',' ')}</button></li>)}{graph.edges.map(e => <li key={e.id}><button onClick={() => { setSelectedEdge(e.id); setSelectedNode(null); setInspectorOpen(true) }}>{graph.nodes.find(n => n.id === e.source)?.label} → {graph.nodes.find(n => n.id === e.target)?.label} · {e.kind} · {e.operation_ids.join(', ')}</button></li>)}</ul></details></div>
    </section>
    <aside className={`inspector side-panel ${inspectorOpen ? 'open' : ''}`} aria-label="Inspector">
      <div className="panel-heading"><h2>Inspector</h2><button className="mobile-close" onClick={() => setInspectorOpen(false)}>Close</button></div>
      {selected ? <>
        <div className="eyebrow">{selected.type.replaceAll('_', ' ')} · Simulated</div>
        <label className="field"><span>Name</span><input value={selected.label} onChange={e => commit(updateNode(graph, selected.id, { label: e.target.value }))}/></label>
        <label className="field" data-guide={selected.type === 'sql_database' ? 'database-profile' : undefined}><span>Profile</span><select value={selected.profile_id} onChange={e => commit(updateNode(graph, selected.id, { profile_id: e.target.value }))}>{catalogue.profiles.filter(p => p.component_type === selected.type).map(p => <option key={p.id} value={p.id}>{p.id}</option>)}</select></label>
        <label className="field"><span>Instances</span><input type="number" min="1" max={['sql_database','object_storage','message_queue','client'].includes(selected.type) ? 1 : 32} value={selected.instance_count} onChange={e => commit(updateNode(graph, selected.id, { instance_count: Number(e.target.value) }))}/></label>
        {(() => { const profile = catalogue.profiles.find(p => p.id === selected.profile_id); return profile && <div className="profile-facts"><h3>Model profile</h3><dl><dt>Slots</dt><dd>{profile.slots}</dd><dt>Queue limit</dt><dd>{profile.queue_limit}</dd><dt>Service time</dt><dd>{profile.service_ms} ms</dd><dt>Credits / hour</dt><dd>{profile.credits_per_hour} × {selected.instance_count}</dd></dl><p>Fixed fictional profile rates. Cloud billing dimensions are omitted.</p></div> })()}
        {Object.entries(catalogue.component_types.find(c => c.type === selected.type)?.settings || {}).length > 0 && <details className="advanced"><summary>Policies and advanced settings</summary>{Object.entries(catalogue.component_types.find(c => c.type === selected.type)?.settings || {}).map(([key, rule]) => { const value = (selected.settings as Record<string, unknown>)[key]; const spec = rule as { min?: number; max?: number; choices?: string[] }; return <label className="field" key={key}><span>{key.replaceAll('_',' ')}</span>{spec.choices ? <select value={String(value ?? spec.choices[0])} onChange={e => commit(updateNode(graph, selected.id, { settings: { ...selected.settings, [key]: e.target.value } }))}>{spec.choices.map(v => <option key={v}>{v}</option>)}</select> : key === 'deduplicate' ? <input type="checkbox" checked={Boolean(value)} onChange={e => commit(updateNode(graph, selected.id, { settings: { ...selected.settings, [key]: e.target.checked } }))}/> : <input type="number" min={spec.min} max={spec.max} value={value === undefined ? '' : Number(value)} placeholder={`Default · ${spec.min}–${spec.max}`} onChange={e => { const settings = { ...selected.settings } as Record<string, unknown>; if (e.target.value) settings[key] = Number(e.target.value); else delete settings[key]; commit(updateNode(graph, selected.id, { settings })) }}/>}</label> })}</details>}
        <button className="secondary" onClick={() => perform(() => duplicateNode(graph, selected.id))}>Duplicate component</button>
      </> : edgeSelected ? <>
        <div className="eyebrow">Connection</div>
        <label className="field"><span>Source</span><select value={edgeSelected.source} onChange={e => commit(updateEdge(graph, edgeSelected.id, { source: e.target.value }))}>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}</select></label>
        <label className="field"><span>Target</span><select value={edgeSelected.target} onChange={e => commit(updateEdge(graph, edgeSelected.id, { target: e.target.value }))}>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}</select></label>
        <label className="field"><span>Relationship</span><select value={edgeSelected.kind} onChange={e => commit(updateEdge(graph, edgeSelected.id, { kind: e.target.value as DesignEdge['kind'] }))}>{(['request','cache_miss','invalidate','consume'] as const).map(k => <option key={k} value={k}>{k.replaceAll('_',' ')}</option>)}</select></label>
        <fieldset><legend>Operations</legend>{challenge.operations.map(o => <label className="check" key={o.id}><input type="checkbox" checked={edgeSelected.operation_ids.includes(o.id)} onChange={e => commit(updateEdge(graph, edgeSelected.id, { operation_ids: e.target.checked ? [...edgeSelected.operation_ids, o.id] : edgeSelected.operation_ids.filter(id => id !== o.id) }))}/>{o.id}</label>)}</fieldset>
        {validation?.findings.filter(f => f.edge_ids.includes(edgeSelected.id)).map(f => <p className="finding" key={f.code}>{f.message}</p>)}
      </> : <div className="inspector-empty" data-guide="connection"><p>Select a component or connection to edit its settings.</p><h3>Add connection</h3><label className="field"><span>From</span><select value={manualSource} onChange={e => setManualSource(e.target.value)}><option value="">Choose source</option>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}</select></label><label className="field"><span>To</span><select value={manualTarget} onChange={e => setManualTarget(e.target.value)}><option value="">Choose target</option>{graph.nodes.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}</select></label><label className="field"><span>Relationship</span><select value={connectKind} onChange={e => setConnectKind(e.target.value as DesignEdge['kind'])}>{(['request','cache_miss','invalidate','consume'] as const).map(k => <option key={k} value={k}>{k.replaceAll('_',' ')}</option>)}</select></label><fieldset><legend>Operations</legend>{challenge.operations.map(o => <label className="check" key={o.id}><input type="checkbox" checked={manualOperations.includes(o.id)} onChange={e => setManualOperations(e.target.checked ? [...manualOperations, o.id] : manualOperations.filter(id => id !== o.id))}/>{o.id}</label>)}</fieldset><button className="primary full" disabled={!manualSource || !manualTarget} onClick={() => connect(manualSource, manualTarget)}>Add connection</button></div>}
      {validation && <div className="validation"><h3>{validation.runnable ? 'Ready to run' : validation.valid_draft ? 'Draft needs routes' : 'Fix design'}</h3>{validation.findings.length ? <ul>{validation.findings.map((f,i) => <li key={i}>{f.message}</li>)}</ul> : <p>All operations have runnable routes.</p>}</div>}
    </aside>
    {showAdd && <Dialog label="Add component" onClose={() => setShowAdd(false)}><div className="panel-heading"><h2>Add component</h2><button onClick={() => setShowAdd(false)}>Close</button></div><label className="field"><span>Search</span><input autoFocus value={paletteSearch} onChange={e => setPaletteSearch(e.target.value)}/></label><div className="palette-list">{visible.map(c => <button key={c.type} className="palette-item" disabled={!challenge.allowed_component_types.includes(c.type as DesignNode['type'])} onClick={() => add(c.type as DesignNode['type'])}>{c.label}<small>{challenge.allowed_component_types.includes(c.type as DesignNode['type']) ? c.purpose : 'Not allowed in this challenge'}</small></button>)}</div></Dialog>}
  </div>
}
